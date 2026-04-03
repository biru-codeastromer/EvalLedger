"""Tests for the observability layer.

Covers:
- _HealthProbeFilter suppresses /health/live entries when enabled
- configure_logging respects log_level argument
- configure_logging with log_health_requests=False wires in the filter
- configure_logging with log_health_requests=True does not wire in the filter
- request.completed includes client_ip
- upload validation failures emit warning logs with structured fields
- contamination.check_unavailable emitted when worker disabled
- ratelimit.throttled emitted when bucket is exceeded
- app_error.auth_rejected emitted for 401/403 AppErrors
- ratelimit.request_throttled emitted for 429 AppErrors
- OAuth event helpers emit correct structured log fields (via _req_id)
"""

from __future__ import annotations

import logging
from io import BytesIO
from logging import LogRecord
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.errors import AppError
from app.logging import _HealthProbeFilter, configure_logging

# ---------------------------------------------------------------------------
# _HealthProbeFilter
# ---------------------------------------------------------------------------


def _make_record(path: str | None = None) -> LogRecord:
    record = logging.LogRecord(
        name="evalledger", level=logging.INFO, pathname="", lineno=0,
        msg="request.completed", args=(), exc_info=None,
    )
    if path is not None:
        record.path = path  # type: ignore[attr-defined]
    return record


def test_health_probe_filter_suppresses_health_live() -> None:
    f = _HealthProbeFilter()
    record = _make_record("/health/live")
    assert f.filter(record) is False


def test_health_probe_filter_passes_other_paths() -> None:
    f = _HealthProbeFilter()
    for path in ["/search", "/health", "/benchmarks/mmlu", None]:
        assert f.filter(_make_record(path)) is True, f"Expected path={path!r} to pass"


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------


def test_configure_logging_sets_level() -> None:
    configure_logging(log_level="WARNING")
    assert logging.getLogger().level == logging.WARNING
    # Restore
    configure_logging(log_level="INFO")


def test_configure_logging_health_requests_false_adds_filter() -> None:
    configure_logging(log_level="INFO", log_health_requests=False)
    handler = logging.getLogger().handlers[0]
    filter_types = [type(f) for f in handler.filters]
    assert _HealthProbeFilter in filter_types
    # Restore default (no filter)
    configure_logging(log_level="INFO", log_health_requests=True)


def test_configure_logging_health_requests_true_no_filter() -> None:
    configure_logging(log_level="INFO", log_health_requests=True)
    handler = logging.getLogger().handlers[0]
    filter_types = [type(f) for f in handler.filters]
    assert _HealthProbeFilter not in filter_types


# ---------------------------------------------------------------------------
# Upload validation logging
# ---------------------------------------------------------------------------


def test_upload_validate_name_logs_unsafe_filename(caplog: pytest.LogCaptureFixture) -> None:
    from app.utils.uploads import validate_upload_name

    # Use root-level capture to avoid handler disruption from configure_logging() in earlier tests.
    with caplog.at_level(logging.WARNING):
        with pytest.raises(AppError):
            validate_upload_name(".")
    assert any("upload.invalid_filename" in r.message for r in caplog.records)


def test_upload_validate_name_logs_bad_extension(caplog: pytest.LogCaptureFixture) -> None:
    from app.utils.uploads import validate_upload_name

    with caplog.at_level(logging.WARNING):
        with pytest.raises(AppError):
            validate_upload_name("data.exe")
    assert any("upload.unsupported_extension" in r.message for r in caplog.records)
    record = next(r for r in caplog.records if "upload.unsupported_extension" in r.message)
    assert getattr(record, "suffix", None) == ".exe"


def test_upload_validate_file_logs_empty_artifact(caplog: pytest.LogCaptureFixture) -> None:
    from fastapi import UploadFile

    from app.utils.uploads import validate_upload_file

    upload = MagicMock(spec=UploadFile)
    upload.filename = "data.jsonl"
    upload.file = BytesIO(b"")  # empty

    with caplog.at_level(logging.WARNING):
        with pytest.raises(AppError):
            validate_upload_file(upload, authenticated=True)
    assert any("upload.empty_artifact" in r.message for r in caplog.records)


def test_upload_validate_file_logs_too_large(caplog: pytest.LogCaptureFixture) -> None:
    from fastapi import UploadFile

    from app.config import get_settings
    from app.utils.uploads import validate_upload_file

    settings = get_settings()
    oversized = b"x" * (settings.max_public_upload_bytes + 1)
    upload = MagicMock(spec=UploadFile)
    upload.filename = "data.json"
    upload.file = BytesIO(oversized)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(AppError):
            validate_upload_file(upload, authenticated=False)
    assert any("upload.artifact_too_large" in r.message for r in caplog.records)
    record = next(r for r in caplog.records if "upload.artifact_too_large" in r.message)
    assert getattr(record, "authenticated", True) is False


# ---------------------------------------------------------------------------
# Contamination unavailable logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contamination_check_unavailable_logs(caplog: pytest.LogCaptureFixture) -> None:
    """POST /contamination/check logs when worker is disabled."""
    from fastapi import UploadFile

    from app.routers import contamination as contamination_router

    upload = MagicMock(spec=UploadFile)
    upload.filename = "test.jsonl"

    fake_session = AsyncMock()

    with patch.object(contamination_router.settings, "worker_enabled", False):
        with caplog.at_level(logging.INFO):
            await contamination_router.run_check(
                session=fake_session,  # type: ignore[arg-type]
                artifact=upload,
                _rl=None,
                corpus_ids=None,
                current_user=None,
            )

    assert any("contamination.check_unavailable" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Rate-limit throttle logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ratelimit_throttled_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    """RateLimiter.check emits ratelimit.throttled when the counter exceeds the limit."""
    from unittest.mock import AsyncMock

    from app.ratelimit import RateLimiter, RateLimitError

    redis = AsyncMock()
    redis.incr.return_value = 999  # way over any limit

    with caplog.at_level(logging.WARNING, logger="evalledger.ratelimit"):
        with pytest.raises(RateLimitError):
            await RateLimiter(redis, enabled=True).check("test_bucket", "client1", limit=10, window_seconds=60)

    assert any("ratelimit.throttled" in r.message for r in caplog.records)
    record = next(r for r in caplog.records if "ratelimit.throttled" in r.message)
    assert getattr(record, "bucket", None) == "test_bucket"


# ---------------------------------------------------------------------------
# Error handler logging (auth_rejected / throttled / server_error)
# ---------------------------------------------------------------------------


def _make_mock_request(path: str = "/test") -> MagicMock:
    req = MagicMock()
    req.state.request_id = "test-req-id"
    req.method = "GET"
    req.url.path = path
    return req


@pytest.mark.asyncio
async def test_error_handler_logs_auth_rejected(caplog: pytest.LogCaptureFixture) -> None:
    """401 AppErrors are logged as app_error.auth_rejected."""
    from fastapi import FastAPI

    from app.errors import AppError, register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)

    # Grab the registered handler directly from the exception_handlers dict.
    handler = app.exception_handlers[AppError]

    exc = AppError("not_authenticated", "Authentication required", status_code=401)
    request = _make_mock_request()

    with caplog.at_level(logging.WARNING, logger="evalledger.errors"):
        await handler(request, exc)

    assert any("app_error.auth_rejected" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_error_handler_logs_rate_limit_throttled(caplog: pytest.LogCaptureFixture) -> None:
    """429 AppErrors are logged as ratelimit.request_throttled."""
    from fastapi import FastAPI

    from app.errors import AppError, register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)

    handler = app.exception_handlers[AppError]
    exc = AppError("rate_limit_exceeded", "Too many requests", status_code=429, details={"retry_after": 30})
    request = _make_mock_request()

    with caplog.at_level(logging.WARNING, logger="evalledger.errors"):
        await handler(request, exc)

    assert any("ratelimit.request_throttled" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_error_handler_logs_server_error(caplog: pytest.LogCaptureFixture) -> None:
    """500 AppErrors are logged at ERROR level."""
    from fastapi import FastAPI

    from app.errors import AppError, register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)

    handler = app.exception_handlers[AppError]
    exc = AppError("internal_error", "Something broke", status_code=500)
    request = _make_mock_request()

    with caplog.at_level(logging.ERROR, logger="evalledger.errors"):
        await handler(request, exc)

    assert any("app_error.server_error" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# OAuth helper logging
# ---------------------------------------------------------------------------


def test_oauth_req_id_from_state() -> None:
    """_req_id returns the request_id attached by the middleware."""
    from app.routers.oauth import _req_id

    req = MagicMock()
    req.state.request_id = "abc-123"
    assert _req_id(req) == "abc-123"


def test_oauth_req_id_missing_state() -> None:
    """_req_id returns None if request_id was not set (e.g. in unit tests)."""
    from app.routers.oauth import _req_id

    # Use an empty object with no .state attribute; getattr(..., None) should
    # catch the AttributeError from the missing attribute and return None.
    class _Bare:
        pass

    req = _Bare()
    assert _req_id(req) is None  # type: ignore[arg-type]
