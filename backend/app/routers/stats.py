from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.dependencies import SessionDep
from app.models.benchmark import Benchmark
from app.models.contamination import ContaminationReport
from app.models.version import BenchmarkVersion
from app.ratelimit import RateLimit

router = APIRouter()
StatsLimit = Annotated[int, Query(ge=1, le=50)]

_stats_rl = Depends(RateLimit("stats", anon_limit=30, auth_limit=60))


@router.get("/overview")
async def overview(session: SessionDep, _rl: Annotated[None, _stats_rl] = None) -> dict[str, int]:
    total_benchmarks = await session.scalar(select(func.count(Benchmark.id)))
    total_versions = await session.scalar(select(func.count(BenchmarkVersion.id)))
    total_checks = await session.scalar(select(func.count(ContaminationReport.id)))
    flagged = await session.scalar(
        select(func.count(BenchmarkVersion.id)).where(
            BenchmarkVersion.contamination_status.in_(["flagged", "contaminated"])
        )
    )
    return {
        "total_benchmarks": total_benchmarks or 0,
        "total_versions": total_versions or 0,
        "contamination_checks": total_checks or 0,
        "benchmarks_flagged": flagged or 0,
    }


@router.get("/recent")
async def recent(
    session: SessionDep,
    _rl: Annotated[None, _stats_rl] = None,
    limit: StatsLimit = 10,
) -> list[dict[str, object]]:
    versions = list(
        (
            await session.scalars(
                select(BenchmarkVersion)
                .options(selectinload(BenchmarkVersion.benchmark))
                .order_by(BenchmarkVersion.created_at.desc())
                .limit(limit)
            )
        ).all()
    )
    return [
        {
            "id": str(version.id),
            "benchmark_slug": version.benchmark.slug,
            "benchmark_name": version.benchmark.name,
            "version": version.version,
            "contamination_status": version.contamination_status,
            "created_at": version.created_at.isoformat(),
        }
        for version in versions
    ]


@router.get("/leaderboard")
async def leaderboard(
    session: SessionDep,
    _rl: Annotated[None, _stats_rl] = None,
    limit: StatsLimit = 10,
) -> list[dict[str, object]]:
    benchmarks = list(
        (
            await session.scalars(
                select(Benchmark).order_by(Benchmark.total_citations.desc(), Benchmark.name.asc()).limit(limit)
            )
        ).all()
    )
    return [
        {
            "slug": benchmark.slug,
            "name": benchmark.name,
            "total_citations": benchmark.total_citations,
            "total_versions": benchmark.total_versions,
        }
        for benchmark in benchmarks
    ]
