from __future__ import annotations

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
from app.errors import register_exception_handlers
from app.logging import configure_logging, logger
from app.ratelimit import set_limiter
from app.routers import admin, auth, benchmarks, contamination, oauth, search, stats, versions
from app.services.storage import StorageService

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


app = FastAPI(
    title="EvalLedger API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


@app.middleware("http")
async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    request_id = request.headers.get("x-request-id") or uuid4().hex
    request.state.request_id = request_id
    # Prefer X-Forwarded-For (Render proxy) over direct client host for IP logging.
    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    started_at = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.info(
            "request.completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
            },
        )
        raise
    duration_ms = round((perf_counter() - started_at) * 1000, 2)
    logger.info(
        "request.completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": client_ip,
        },
    )
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
