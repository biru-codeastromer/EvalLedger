"""Unit tests for the Redis-backed rate limiting module (app/ratelimit.py)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ratelimit import (
    RateLimit,
    RateLimiter,
    RateLimitError,
    get_client_id,
    is_authenticated,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(
    *,
    api_key: str | None = None,
    authorization: str | None = None,
    forwarded_for: str | None = None,
    client_host: str = "127.0.0.1",
) -> MagicMock:
    """Build a minimal mock ``fastapi.Request`` with only the attributes under test."""
    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key
    if authorization:
        headers["authorization"] = authorization
    if forwarded_for:
        headers["x-forwarded-for"] = forwarded_for

    request = MagicMock()
    request.headers = headers
    client = MagicMock()
    client.host = client_host
    request.client = client
    return request


# ---------------------------------------------------------------------------
# RateLimitError
# ---------------------------------------------------------------------------


def test_rate_limit_error_attributes() -> None:
    exc = RateLimitError(retry_after=42)
    assert exc.status_code == 429
    assert exc.code == "rate_limit_exceeded"
    assert exc.details is not None
    assert exc.details["retry_after"] == 42
    assert exc.retry_after == 42


# ---------------------------------------------------------------------------
# get_client_id
# ---------------------------------------------------------------------------


def test_get_client_id_prefers_api_key() -> None:
    req = _make_request(api_key="el_abc123", forwarded_for="10.0.0.1", authorization="Bearer tok")
    cid = get_client_id(req)
    assert cid.startswith("key:")
    # Different raw keys must hash to different identifiers.
    req2 = _make_request(api_key="el_different")
    assert get_client_id(req2) != cid


def test_get_client_id_falls_back_to_bearer() -> None:
    req = _make_request(authorization="Bearer mytoken", forwarded_for="10.0.0.1")
    cid = get_client_id(req)
    assert cid.startswith("tok:")


def test_get_client_id_falls_back_to_forwarded_for() -> None:
    req = _make_request(forwarded_for="203.0.113.5, 10.0.0.1")
    cid = get_client_id(req)
    # Takes the leftmost (original) IP only.
    assert cid == "ip:203.0.113.5"


def test_get_client_id_falls_back_to_direct_ip() -> None:
    req = _make_request(client_host="192.168.1.100")
    cid = get_client_id(req)
    assert cid == "ip:192.168.1.100"


def test_get_client_id_hides_raw_api_key() -> None:
    """The raw API key must never appear in the client-id string."""
    raw_key = "el_supersecretkey"
    req = _make_request(api_key=raw_key)
    assert raw_key not in get_client_id(req)


# ---------------------------------------------------------------------------
# is_authenticated
# ---------------------------------------------------------------------------


def test_is_authenticated_with_api_key() -> None:
    assert is_authenticated(_make_request(api_key="el_key")) is True


def test_is_authenticated_with_bearer() -> None:
    assert is_authenticated(_make_request(authorization="Bearer tok")) is True


def test_is_authenticated_anonymous() -> None:
    assert is_authenticated(_make_request()) is False


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limiter_allows_requests_within_limit() -> None:
    redis = AsyncMock()
    redis.incr.return_value = 1
    limiter = RateLimiter(redis, enabled=True)
    # Must not raise.
    await limiter.check("test", "client1", limit=10, window_seconds=60)
    redis.incr.assert_called_once()
    redis.expire.assert_called_once()


@pytest.mark.asyncio
async def test_rate_limiter_raises_when_over_limit() -> None:
    redis = AsyncMock()
    redis.incr.return_value = 11  # Over a limit of 10.
    limiter = RateLimiter(redis, enabled=True)
    with pytest.raises(RateLimitError) as exc_info:
        await limiter.check("test", "client1", limit=10, window_seconds=60)
    assert exc_info.value.retry_after >= 1


@pytest.mark.asyncio
async def test_rate_limiter_no_expire_on_subsequent_increments() -> None:
    """expire should only be set on the first request (count == 1)."""
    redis = AsyncMock()
    redis.incr.return_value = 5  # Not the first request.
    limiter = RateLimiter(redis, enabled=True)
    await limiter.check("test", "client1", limit=10, window_seconds=60)
    redis.expire.assert_not_called()


@pytest.mark.asyncio
async def test_rate_limiter_fail_open_on_redis_error() -> None:
    """A Redis failure must allow the request through (fail-open)."""
    redis = AsyncMock()
    redis.incr.side_effect = ConnectionError("Redis down")
    limiter = RateLimiter(redis, enabled=True)
    # Must not raise RateLimitError — fails open.
    await limiter.check("test", "client1", limit=10, window_seconds=60)


@pytest.mark.asyncio
async def test_rate_limiter_disabled_skips_redis() -> None:
    redis = AsyncMock()
    limiter = RateLimiter(redis, enabled=False)
    await limiter.check("test", "client1", limit=0, window_seconds=60)
    redis.incr.assert_not_called()


@pytest.mark.asyncio
async def test_rate_limiter_no_redis_skips_check() -> None:
    limiter = RateLimiter(None, enabled=True)
    # Must not raise — no Redis client attached.
    await limiter.check("test", "client1", limit=0, window_seconds=60)


# ---------------------------------------------------------------------------
# RateLimit FastAPI dependency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_dependency_passes_when_enabled_and_under_limit() -> None:
    redis = AsyncMock()
    redis.incr.return_value = 1

    with (
        patch("app.ratelimit.get_limiter", return_value=redis),
        patch("app.ratelimit.RateLimiter.check", new_callable=AsyncMock) as mock_check,
    ):
        mock_check.return_value = None
        dep = RateLimit("test", anon_limit=60, auth_limit=120)
        request = _make_request()
        # Must not raise.
        await dep(request)
        mock_check.assert_called_once()


@pytest.mark.asyncio
async def test_rate_limit_dependency_uses_auth_limit_for_authenticated() -> None:
    """Authenticated requests should be checked against the higher auth_limit."""
    calls: list[tuple[str, str, int, int]] = []

    # Patching an instance method passes `self` as the first argument.
    async def _capture(_self: object, name: str, client_id: str, limit: int, window_seconds: int) -> None:
        calls.append((name, client_id, limit, window_seconds))

    with patch("app.ratelimit.RateLimiter.check", new=_capture):
        dep = RateLimit("test", anon_limit=30, auth_limit=120)
        request = _make_request(api_key="el_somekey")
        with patch("app.config.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_enabled = True
            await dep(request)

    assert calls[0][2] == 120  # auth_limit passed to check


@pytest.mark.asyncio
async def test_rate_limit_dependency_uses_anon_limit_for_unauthenticated() -> None:
    calls: list[tuple[str, str, int, int]] = []

    async def _capture(_self: object, name: str, client_id: str, limit: int, window_seconds: int) -> None:
        calls.append((name, client_id, limit, window_seconds))

    with patch("app.ratelimit.RateLimiter.check", new=_capture):
        dep = RateLimit("test", anon_limit=30, auth_limit=120)
        request = _make_request()  # No API key or Bearer token.
        with patch("app.config.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_enabled = True
            await dep(request)

    assert calls[0][2] == 30  # anon_limit used
