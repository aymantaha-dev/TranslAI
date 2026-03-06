"""Authentication utilities for protected API endpoints."""

from typing import Optional

from fastapi import Header, HTTPException, status

from .config import settings


async def require_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> str:
    """Require a valid API key for protected endpoints.

    Supports either:
    - `X-API-Key: <key>`
    - `Authorization: Bearer <key>`
    """
    if not settings.auth_enabled:
        return "auth-disabled"

    token = x_api_key
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Missing API key", "code": "AUTH_REQUIRED"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    valid_keys = settings.parsed_api_keys()
    if token not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Invalid API key", "code": "INVALID_API_KEY"},
        )

    return token
