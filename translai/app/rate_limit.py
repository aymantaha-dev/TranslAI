"""Async rate limiting middleware with in-memory token bucket and optional Redis backend."""

import asyncio
import time
from collections import defaultdict
from typing import Dict, Optional, Tuple

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .logger import get_request_logger

try:
    import redis.asyncio as redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None


class InMemoryTokenBucket:
    """Simple async-safe token bucket implementation per key."""

    def __init__(self, capacity: int, window_seconds: int):
        self.capacity = capacity
        self.window_seconds = window_seconds
        self.refill_rate = capacity / window_seconds
        self._buckets: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"tokens": float(capacity), "last_refill": time.time()}
        )
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> Tuple[bool, float]:
        async with self._lock:
            now = time.time()
            bucket = self._buckets[key]
            elapsed = now - bucket["last_refill"]
            bucket["tokens"] = min(self.capacity, bucket["tokens"] + elapsed * self.refill_rate)
            bucket["last_refill"] = now

            if bucket["tokens"] >= 1.0:
                bucket["tokens"] -= 1.0
                return True, 0.0

            retry_after = (1.0 - bucket["tokens"]) / self.refill_rate
            return False, max(retry_after, 0.1)


class RateLimiter:
    """Rate limiter with optional Redis storage and in-memory fallback."""

    def __init__(self):
        self.memory = InMemoryTokenBucket(settings.rate_limit_requests, settings.rate_limit_window)
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=True) if (settings.redis_url and redis) else None

    async def allow(self, key: str) -> Tuple[bool, float]:
        if not self.redis_client:
            return await self.memory.allow(key)

        # Lightweight Redis fallback window counter (async safe)
        now = int(time.time())
        window = settings.rate_limit_window
        bucket = now // window
        redis_key = f"rl:{key}:{bucket}"

        count = await self.redis_client.incr(redis_key)
        if count == 1:
            await self.redis_client.expire(redis_key, window)

        if count <= settings.rate_limit_requests:
            return True, 0.0

        ttl = await self.redis_client.ttl(redis_key)
        return False, float(max(ttl, 1))

    async def close(self):
        if self.redis_client:
            await self.redis_client.aclose()


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit incoming requests per client key or IP."""

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        api_key = request.headers.get("x-api-key")
        identifier = api_key or client_ip

        allowed, retry_after = await rate_limiter.allow(identifier)
        if not allowed:
            logger = get_request_logger(request.headers.get("X-Request-ID"))
            logger.warning("Rate limit exceeded", extra={"client": identifier, "retry_after": retry_after})
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "details": {"retry_after": retry_after},
                },
                headers={"Retry-After": str(int(retry_after))},
            )

        return await call_next(request)
