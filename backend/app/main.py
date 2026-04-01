from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import register_exception_handlers
from app.logging import configure_logging
from app.routers import auth, benchmarks, contamination, search, stats, versions
from app.services.storage import StorageService

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    await StorageService.from_settings(settings).ensure_ready()
    yield


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

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(benchmarks.router, prefix="/benchmarks", tags=["benchmarks"])
app.include_router(versions.router, prefix="/benchmarks", tags=["versions"])
app.include_router(search.router, tags=["search", "stats"])
app.include_router(contamination.router, prefix="/contamination", tags=["contamination"])
app.include_router(stats.router, prefix="/stats", tags=["stats"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
