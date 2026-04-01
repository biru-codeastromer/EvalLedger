from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import AdminUser, SessionDep
from app.errors import AppError
from app.models.audit import AuditEvent
from app.models.benchmark import Benchmark
from app.schemas.admin import BenchmarkVerificationRequest, BenchmarkVerificationResponse
from app.schemas.audit import AuditEventResponse
from app.schemas.benchmark import BenchmarkDetail, BenchmarkListItem
from app.services.audit import record_audit_event

router = APIRouter()
AdminLimit = Annotated[int, Query(ge=1, le=100)]


def _benchmark_detail(benchmark: Benchmark) -> BenchmarkDetail:
    latest_version = benchmark.versions[0] if benchmark.versions else None
    item = BenchmarkListItem(
        id=benchmark.id,
        slug=benchmark.slug,
        name=benchmark.name,
        description=benchmark.description,
        domain=benchmark.domain,
        task_type=benchmark.task_type,
        is_verified=benchmark.is_verified,
        total_versions=benchmark.total_versions,
        total_citations=benchmark.total_citations,
        created_at=benchmark.created_at,
        updated_at=benchmark.updated_at,
        latest_version=latest_version.version if latest_version else None,
        latest_contamination_status=latest_version.contamination_status if latest_version else None,
        latest_num_examples=latest_version.num_examples if latest_version else None,
    )
    return BenchmarkDetail(**item.model_dump(), submitter=benchmark.submitter)


@router.get("/review-queue", response_model=list[BenchmarkDetail])
async def review_queue(session: SessionDep, _: AdminUser, limit: AdminLimit = 50) -> list[BenchmarkDetail]:
    benchmarks = list(
        (
            await session.scalars(
                select(Benchmark)
                .options(selectinload(Benchmark.submitter), selectinload(Benchmark.versions))
                .where(Benchmark.is_verified.is_(False))
                .order_by(Benchmark.created_at.desc())
                .limit(limit)
            )
        ).all()
    )
    return [_benchmark_detail(item) for item in benchmarks]


@router.get("/audit-events", response_model=list[AuditEventResponse])
async def recent_audit_events(session: SessionDep, _: AdminUser, limit: AdminLimit = 100) -> list[AuditEventResponse]:
    events = list(
        (
            await session.scalars(
                select(AuditEvent)
                .options(selectinload(AuditEvent.actor))
                .order_by(AuditEvent.created_at.desc())
                .limit(limit)
            )
        ).all()
    )
    return [AuditEventResponse.model_validate(item) for item in events]


@router.patch("/benchmarks/{slug}/verification", response_model=BenchmarkVerificationResponse)
async def set_benchmark_verification(
    slug: str,
    payload: BenchmarkVerificationRequest,
    session: SessionDep,
    current_user: AdminUser,
) -> BenchmarkVerificationResponse:
    benchmark = await session.scalar(
        select(Benchmark)
        .options(selectinload(Benchmark.submitter), selectinload(Benchmark.versions))
        .where(Benchmark.slug == slug)
    )
    if benchmark is None:
        raise AppError("benchmark_not_found", "Benchmark not found", status_code=404)
    benchmark.is_verified = payload.verified
    await session.flush()
    await record_audit_event(
        session,
        action="benchmark.verified" if payload.verified else "benchmark.unverified",
        actor=current_user,
        benchmark=benchmark,
        resource_type="benchmark",
        resource_id=str(benchmark.id),
        resource_slug=benchmark.slug,
        summary=payload.note
        or ("Marked benchmark as verified" if payload.verified else "Removed benchmark verification"),
        metadata={"verified": payload.verified},
    )
    await session.commit()
    await session.refresh(benchmark)
    return BenchmarkVerificationResponse(benchmark=_benchmark_detail(benchmark))
