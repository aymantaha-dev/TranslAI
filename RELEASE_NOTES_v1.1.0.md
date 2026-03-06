# RELEASE NOTES v1.1.0

## Security/Authentication
- Added API key authentication via `X-API-Key` or `Authorization: Bearer <key>`.
- Protected sensitive endpoints:
  - `POST /api/v1/generate`
  - `GET /api/v1/user`
  - `GET /api/v1/memory`
  - provider listing and config endpoints.
- Added proper authentication error handling:
  - `401` for missing credentials.
  - `403` for invalid credentials.

## Rate Limiting
- Added async rate-limiting middleware.
- Enforces per-client quotas using token-bucket logic.
- Supports optional Redis-backed counters when `REDIS_URL` is configured.
- Returns `429` with `Retry-After` header when quota is exceeded.

## Provider Lifecycle
- Implemented provider instance registry.
- Tracks text and image provider clients created during request processing.
- Added graceful async cleanup during app shutdown.
- Implemented rate limiter shutdown cleanup for Redis connections.

## Language Detection
- Standardized language detection on `fast-langdetect`.
- Added robust fallback path for restricted networks or model download failures.
- Added offline heuristic fallback (Arabic vs English baseline) to prevent crashes.

## Dependency/Env
- Updated `.env.example` with auth, rate-limit, Redis, and version settings.
- Added `redis` dependency for optional distributed rate limiting.
- Removed legacy README guidance for `langdetect`; now references `fast-langdetect` only.
- Added graceful warnings for missing provider API keys and missing auth key configuration.

## Tests Added
- Added automated tests for:
  - Health endpoint (`/api/health`).
  - Config loading without provider keys.
  - Language detection fallback behavior.
  - Generate endpoint validation and auth enforcement.

## Version Bump
- Bumped application version from `1.0.0` to `1.1.0` in runtime configuration and API metadata.
