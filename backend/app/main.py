from __future__ import annotations

import hashlib
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from starlette.responses import Response

from app.config import get_settings
from app.database import engine
from app.errors import error_response, register_exception_handlers
from app.idempotency import (
    IDEMPOTENCY_HEADER,
    build_idempotency_key,
    decode_cached_response,
    encode_cached_response,
)
from app.logging import configure_logging, logger
from app.metrics import observe_request, render_latest
from app.ratelimit import get_limiter, set_limiter
from app.routers import admin, auth, benchmarks, contamination, oauth, reports, search, stats, versions
from app.services.storage import StorageService

# Paths that must never be cached or counted as cacheable public data.
_CACHE_EXEMPT_PREFIXES = ("/health", "/metrics", "/docs", "/redoc", "/openapi.json")

_OPENAPI_TAGS = [
    {"name": "auth", "description": "Sign-in (OAuth), the current user, and API-key management."},
    {"name": "benchmarks", "description": "Benchmark registration, metadata, and discovery."},
    {"name": "versions", "description": "Versioned artifact submission, download, and citations."},
    {"name": "contamination", "description": "MinHash/LSH contamination reports and ad-hoc checks."},
    {"name": "search", "description": "Full-text search across the registry."},
    {"name": "stats", "description": "Aggregate registry statistics and recent activity."},
    {"name": "admin", "description": "Maintainer review and verification workflow."},
    {"name": "reports", "description": "Abuse/takedown reports and the moderation queue."},
]

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(
        log_level=settings.log_level,
        log_health_requests=settings.log_health_requests,
    )
    logger.info(
        "app.startup",
        extra={
            "app_env": settings.app_env,
            "app_version": "0.1.0",
            "worker_enabled": settings.worker_enabled,
            "rate_limit_enabled": settings.rate_limit_enabled,
            "storage_backend": settings.storage_backend,
            # Render injects RENDER_GIT_COMMIT at deploy time; falls back to
            # "unknown" in local/test environments.
            "git_commit": os.environ.get("RENDER_GIT_COMMIT", "unknown"),
        },
    )

    try:
        await StorageService.from_settings(settings).ensure_ready()
    except Exception:
        logger.error("app.startup_storage_failed", exc_info=True)

    # Attach a shared Redis client to the rate-limiter module.  Failures here
    # are non-fatal: set_limiter(None) keeps the limiter in fail-open mode.
    redis_client: Redis | None = None
    try:
        redis_client = Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=False)
        await redis_client.ping()
        set_limiter(redis_client)
        logger.info("ratelimit.redis_connected")
    except Exception:
        logger.warning("ratelimit.redis_unavailable — rate limiting disabled", exc_info=True)
        set_limiter(None)
    try:
        yield
    finally:
        logger.info("app.shutdown")
        set_limiter(None)
        if redis_client is not None:
            await redis_client.aclose()
        await engine.dispose()


app = FastAPI(
    title="EvalLedger API",
    version="0.1.0",
    description=(
        "Registry for AI benchmark provenance: citable versions, verifiable artifact "
        "hashes, and inspectable contamination reports. Public read endpoints are "
        "rate-limited and emit `X-RateLimit-*` headers; cacheable responses carry an "
        "`ETag`. POST writes accept an `Idempotency-Key` header for safe retries. "
        "Operational metrics are exposed at `/metrics` (Prometheus)."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    contact={"name": "EvalLedger", "url": "https://evalledger.dev"},
    license_info={"name": "See repository LICENSE"},
    terms_of_service=f"{settings.frontend_url}/terms",
    openapi_tags=_OPENAPI_TAGS,
    servers=[{"url": settings.app_url, "description": settings.app_env}],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

register_exception_handlers(app)


def _client_ip(request: Request) -> str:
    """Resolve the real client IP, honouring trusted reverse-proxy hops.

    ``trusted_proxy_count`` is how many proxies sit in front of the app (e.g.
    Render's load balancer).  X-Forwarded-For is appended left-to-right, so the
    client's address is the hop ``trusted_proxy_count`` from the right.  When
    fewer hops are present than configured, we clamp to the left-most element.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    if hops:
        # Mirror app.ratelimit._client_ip exactly so the audit log and the
        # rate-limit bucket attribute a caller to the same IP. Clamp to >=1
        # trusted proxy and index from the right.
        proxy_count = max(1, settings.trusted_proxy_count)
        index = max(0, len(hops) - proxy_count)
        return hops[index]
    return request.client.host if request.client else "unknown"


def _content_length_exceeds(request: Request, limit: int) -> bool:
    """Return True only if a well-formed Content-Length header exceeds *limit*.

    A missing or malformed header is treated as 'not over the limit' rather than
    raising — uvicorn rejects invalid Content-Length at the protocol layer, and
    the per-endpoint upload validators enforce real size limits downstream.
    """
    raw = request.headers.get("content-length")
    if raw is None:
        return False
    try:
        return int(raw) > limit
    except ValueError:
        return False


def _apply_http_caching(request: Request, response: Response) -> Response:
    """Add ETag / Cache-Control to safe GETs and short-circuit 304 Not Modified.

    Authenticated requests (which carry per-user data) get ``private, no-store``
    and no shared ETag. Anonymous GETs of public registry data get a weak ETag
    plus ``public, max-age`` so CDNs/browsers can revalidate cheaply. Health,
    metrics and docs paths are exempt entirely.
    """
    if request.method != "GET" or response.status_code != 200:
        return response
    if request.url.path.startswith(_CACHE_EXEMPT_PREFIXES):
        return response
    if request.headers.get("authorization") or request.headers.get("x-api-key"):
        response.headers.setdefault("Cache-Control", "private, no-store")
        return response
    body = getattr(response, "body", None)
    if not isinstance(body, bytes | bytearray):
        return response
    etag = 'W/"' + hashlib.sha256(bytes(body)).hexdigest()[:32] + '"'
    response.headers["ETag"] = etag
    response.headers.setdefault("Cache-Control", f"public, max-age={settings.http_cache_max_age}")
    if request.headers.get("if-none-match") == etag:
        not_modified = Response(status_code=304)
        not_modified.headers["ETag"] = etag
        not_modified.headers["Cache-Control"] = response.headers["Cache-Control"]
        return not_modified
    return response


def _record_metrics(request: Request, status_code: int, duration_seconds: float) -> None:
    route = request.scope.get("route")
    path_label = getattr(route, "path", None) or "unmatched"
    observe_request(request.method, path_label, status_code, duration_seconds)


@app.middleware("http")
async def idempotency(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Opt-in Idempotency-Key replay for POST writes (no-op without the header).

    Defined before request_context so it nests *inside* it — replays still pass
    through request_context for X-Request-ID, metrics and logging.
    """
    idem_key = request.headers.get(IDEMPOTENCY_HEADER)
    redis = get_limiter()
    if request.method != "POST" or not idem_key or redis is None:
        return await call_next(request)

    credential = (
        request.headers.get("authorization") or request.headers.get("x-api-key") or _client_ip(request)
    )
    redis_key = build_idempotency_key(credential, request.url.path, idem_key)

    try:
        cached = await redis.get(redis_key)
    except Exception:
        cached = None  # fail open on Redis error
    if cached:
        try:
            status_code, content_type, body = decode_cached_response(cached)
            replay = Response(content=body, status_code=status_code, media_type=content_type)
            replay.headers["Idempotency-Replay"] = "true"
            return replay
        except ValueError:
            pass  # corrupt cache entry — recompute

    response = await call_next(request)
    body_iterator = getattr(response, "body_iterator", None)
    if body_iterator is None:
        return response  # non-streaming response we can't buffer; pass through
    body = b""
    async for chunk in body_iterator:
        body += chunk
    if response.status_code < 500:
        try:
            await redis.set(
                redis_key,
                encode_cached_response(
                    response.status_code,
                    response.media_type or response.headers.get("content-type", "application/json"),
                    body,
                ),
                ex=settings.idempotency_ttl_seconds,
                nx=True,
            )
        except Exception:
            pass  # fail open on Redis error
    rebuilt = Response(content=body, status_code=response.status_code, media_type=response.media_type)
    for header_key, header_value in response.headers.items():
        if header_key.lower() != "content-length":
            rebuilt.headers[header_key] = header_value
    return rebuilt


@app.middleware("http")
async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    request_id = request.headers.get("x-request-id") or uuid4().hex
    request.state.request_id = request_id
    client_ip = _client_ip(request)
    started_at = perf_counter()
    try:
        if _content_length_exceeds(request, settings.max_request_body_bytes):
            # Reject oversized payloads up front; still flows through the shared
            # logging + X-Request-ID finalisation below.
            response: Response = error_response(
                "payload_too_large",
                "Request body too large",
                status_code=413,
                details={"request_id": request_id, "limit_bytes": settings.max_request_body_bytes},
            )
        else:
            response = await call_next(request)
    except Exception:
        duration_s = perf_counter() - started_at
        _record_metrics(request, 500, duration_s)
        logger.info(
            "request.completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                "duration_ms": round(duration_s * 1000, 2),
                "client_ip": client_ip,
            },
        )
        raise
    duration_s = perf_counter() - started_at
    _record_metrics(request, response.status_code, duration_s)
    logger.info(
        "request.completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_s * 1000, 2),
            "client_ip": client_ip,
        },
    )
    response = _apply_http_caching(request, response)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(oauth.router, prefix="/auth/oauth", tags=["auth"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(benchmarks.router, prefix="/benchmarks", tags=["benchmarks"])
app.include_router(versions.router, prefix="/benchmarks", tags=["versions"])
app.include_router(search.router, tags=["search", "stats"])
app.include_router(contamination.router, prefix="/contamination", tags=["contamination"])
app.include_router(stats.router, prefix="/stats", tags=["stats"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus exposition of the RED metrics (request rate, errors, duration)."""
    payload, content_type = render_latest()
    return Response(content=payload, media_type=content_type)


async def _database_ready() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("health.database_failed")
        return False


async def _redis_ready() -> bool:
    client = Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    try:
        return bool(await client.ping())
    except Exception:
        logger.exception("health.redis_failed")
        return False
    finally:
        await client.aclose()


async def _storage_ready() -> bool:
    try:
        await StorageService.from_settings(settings).ensure_ready()
        return True
    except Exception:
        logger.exception("health.storage_failed")
        return False


@app.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health")
async def health() -> JSONResponse:
    checks = {
        "database": await _database_ready(),
        "redis": await _redis_ready(),
        "storage": await _storage_ready(),
    }
    status_code = 200 if all(checks.values()) else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if status_code == 200 else "degraded", "checks": checks},
    )
