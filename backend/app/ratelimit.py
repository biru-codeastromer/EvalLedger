"""Production-grade Redis-backed rate limiting for EvalLedger.

Design
------
* Fixed-window counter stored in Redis.
  Key schema: ``rl:{name}:{client_id}:{window_slot}``
  where ``window_slot = int(time.time()) // window_seconds``.

* Client identity priority (most to least specific):
    1. X-API-Key header              → SHA-256 prefix (16 hex chars)
    2. Authorization: Bearer …       → SHA-256 prefix
    3. X-Forwarded-For first hop     → raw IP (already an opaque network id)
    4. Direct client IP

* Fail-open: if Redis is unavailable, the request is allowed through and a
  WARNING is logged.  The API stays up during Redis restarts.

* Disabled globally via ``RATE_LIMIT_ENABLED=false`` (useful in tests).

Usage
-----
    from typing import Annotated
    from fastapi import Depends
    from app.ratelimit import RateLimit

    @router.get("/search")
    async def search(
        _rl: Annotated[None, Depends(RateLimit("search", anon_limit=60, auth_limit=120))],
        ...
    ) -> ...:
        ...
"""

from __future__ import annotations

import hashlib
import logging
import time

from fastapi import Request, status
from redis.asyncio import Redis

from app.errors import AppError

logger = logging.getLogger("evalledger.ratelimit")

# ---------------------------------------------------------------------------
# Singleton Redis client (set during app lifespan / tests via set_limiter)
# ---------------------------------------------------------------------------

_limiter: Redis | None = None


def set_limiter(client: Redis | None) -> None:
    """Attach a Redis client to the module-level singleton."""
    global _limiter
    _limiter = client


def get_limiter() -> Redis | None:
    """Return the module-level Redis client (may be None)."""
    return _limiter


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class RateLimitError(AppError):
    """Raised when a client exceeds its allowed request rate."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(
            code="rate_limit_exceeded",
            message="Too many requests — please slow down and retry shortly.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after": retry_after},
        )
        self.retry_after = retry_after


# ---------------------------------------------------------------------------
# Client identity
# ---------------------------------------------------------------------------


def _sha256_prefix(value: str) -> str:
    """Return the first 16 hex chars of the SHA-256 digest of *value*."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def get_client_id(request: Request) -> str:
    """Return a stable, opaque identifier for the caller.

    Priority:
    1. X-API-Key header (hashed — raw token never appears in Redis)
    2. Authorization: Bearer … (hashed)
    3. X-Forwarded-For first IP (leftmost = original client behind Render proxy)
    4. Direct ``request.client.host``
    """
    api_key = request.headers.get("x-api-key")
    if api_key:
        return f"key:{_sha256_prefix(api_key)}"

    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return f"tok:{_sha256_prefix(token)}"

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
        return f"ip:{ip}"

    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def is_authenticated(request: Request) -> bool:
    """Return True if the request carries an API key or Bearer token."""
    return bool(
        request.headers.get("x-api-key")
        or request.headers.get("authorization", "").lower().startswith("bearer ")
    )


# ---------------------------------------------------------------------------
# Core limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Fixed-window Redis rate limiter.

    Parameters
    ----------
    redis:
        Async Redis client.  ``None`` → no-op (fail-open).
    enabled:
        When ``False`` every call is a no-op regardless of Redis state.
        Controlled by ``Settings.rate_limit_enabled``.
    """

    def __init__(self, redis: Redis | None, *, enabled: bool = True) -> None:
        self._redis = redis
        self._enabled = enabled

    async def check(
        self,
        name: str,
        client_id: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        """Increment the counter; raise :exc:`RateLimitError` when over limit.

        Fail-open: any Redis error is logged at WARNING level and the request
        is allowed through.
        """
        if not self._enabled or self._redis is None:
            return

        window_slot = int(time.time()) // window_seconds
        key = f"rl:{name}:{client_id}:{window_slot}"

        try:
            count = await self._redis.incr(key)
            if count == 1:
                # Set TTL to 2x window so the key outlives the window by one
                # slot, preventing a brief gap where a burst could reset the
                # counter prematurely.
                await self._redis.expire(key, window_seconds * 2)
            if count > limit:
                retry_after = window_seconds - (int(time.time()) % window_seconds)
                raise RateLimitError(retry_after=max(1, retry_after))
        except RateLimitError:
            raise
        except Exception:
            logger.warning("ratelimit.redis_error — failing open", exc_info=True)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


class RateLimit:
    """FastAPI dependency that enforces a per-route fixed-window rate limit.

    Authenticated callers (API key or Bearer token) receive the higher
    ``auth_limit`` bucket; anonymous callers receive ``anon_limit``.

    Parameters
    ----------
    name:
        Unique bucket name used in the Redis key (e.g. ``"search"``).
    anon_limit:
        Max requests per window for unauthenticated clients.
    auth_limit:
        Max requests per window for authenticated clients.  Defaults to
        ``anon_limit`` when omitted.
    window_seconds:
        Length of the fixed window in seconds (default: 60 s).

    Example::

        from typing import Annotated
        from fastapi import Depends
        from app.ratelimit import RateLimit

        @router.get("/search")
        async def search(
            _rl: Annotated[None, Depends(RateLimit("search", anon_limit=60, auth_limit=120))],
        ) -> ...:
            ...
    """

    def __init__(
        self,
        name: str,
        *,
        anon_limit: int,
        auth_limit: int | None = None,
        window_seconds: int = 60,
    ) -> None:
        self.name = name
        self.anon_limit = anon_limit
        self.auth_limit = auth_limit if auth_limit is not None else anon_limit
        self.window_seconds = window_seconds

    async def __call__(self, request: Request) -> None:
        from app.config import get_settings

        settings = get_settings()
        limiter = RateLimiter(get_limiter(), enabled=settings.rate_limit_enabled)
        client_id = get_client_id(request)
        limit = self.auth_limit if is_authenticated(request) else self.anon_limit
        await limiter.check(self.name, client_id, limit, self.window_seconds)
