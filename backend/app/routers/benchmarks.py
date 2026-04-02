from __future__ import annotations

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.dependencies import CurrentUser, SessionDep
from app.errors import AppError
from app.models.audit import AuditEvent
from app.models.benchmark import Benchmark
from app.schemas.audit import AuditEventResponse
from app.schemas.benchmark import (
    BenchmarkCreate,
    BenchmarkDetail,
    BenchmarkListItem,
    BenchmarkListResponse,
    BenchmarkUpdate,
)
from app.services.audit import record_audit_event

router = APIRouter()


def _benchmark_item(benchmark: Benchmark) -> BenchmarkListItem:
    latest_version = benchmark.versions[0] if benchmark.versions else None
    return BenchmarkListItem(
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


@router.get("", response_model=BenchmarkListResponse)
async def list_benchmarks(
    session: SessionDep,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> BenchmarkListResponse:
    total = await session.scalar(select(func.count(Benchmark.id)))
    benchmarks = list(
        (
            await session.scalars(
                select(Benchmark)
                .options(selectinload(Benchmark.versions))
                .order_by(Benchmark.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).all()
    )
    return BenchmarkListResponse(
        page=page,
        limit=limit,
        total=total or 0,
        items=[_benchmark_item(benchmark) for benchmark in benchmarks],
    )


@router.get("/{slug}", response_model=BenchmarkDetail)
async def get_benchmark(slug: str, session: SessionDep) -> BenchmarkDetail:
    benchmark = await session.scalar(
        select(Benchmark)
        .options(selectinload(Benchmark.versions), selectinload(Benchmark.submitter))
        .where(Benchmark.slug == slug)
    )
    if benchmark is None:
        raise AppError("benchmark_not_found", "Benchmark not found", status_code=404)
    item = _benchmark_item(benchmark)
    return BenchmarkDetail(**item.model_dump(), submitter=benchmark.submitter)


@router.post("", response_model=BenchmarkDetail, status_code=status.HTTP_201_CREATED)
async def create_benchmark(
    payload: BenchmarkCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> BenchmarkDetail:
    existing = await session.scalar(select(Benchmark).where(Benchmark.slug == payload.slug))
    if existing is not None:
        raise AppError("benchmark_exists", "A benchmark with that slug already exists", status_code=409)

    benchmark = Benchmark(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        domain=payload.domain,
        task_type=payload.task_type,
        submitter_id=current_user.id,
    )
    session.add(benchmark)
    await session.flush()
    await record_audit_event(
        session,
        action="benchmark.created",
        actor=current_user,
        benchmark=benchmark,
        resource_type="benchmark",
        resource_id=str(benchmark.id),
        resource_slug=benchmark.slug,
        summary=f"Created benchmark {benchmark.slug}",
    )
    await session.commit()
    created = await session.scalar(
        select(Benchmark)
        .options(selectinload(Benchmark.versions), selectinload(Benchmark.submitter))
        .where(Benchmark.id == benchmark.id)
    )
    assert created is not None
    item = _benchmark_item(created)
    return BenchmarkDetail(**item.model_dump(), submitter=created.submitter)


@router.patch("/{slug}", response_model=BenchmarkDetail)
async def update_benchmark(
    slug: str,
    payload: BenchmarkUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> BenchmarkDetail:
    benchmark = await session.scalar(
        select(Benchmark)
        .options(selectinload(Benchmark.versions), selectinload(Benchmark.submitter))
        .where(Benchmark.slug == slug)
    )
    if benchmark is None:
        raise AppError("benchmark_not_found", "Benchmark not found", status_code=404)
    if benchmark.submitter_id != current_user.id:
        raise AppError("forbidden", "Only the original submitter can edit this benchmark", status_code=403)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(benchmark, field, value)
    await session.flush()
    await record_audit_event(
        session,
        action="benchmark.updated",
        actor=current_user,
        benchmark=benchmark,
        resource_type="benchmark",
        resource_id=str(benchmark.id),
        resource_slug=benchmark.slug,
        summary=f"Updated benchmark {benchmark.slug}",
    )
    await session.commit()
    await session.refresh(benchmark)
    item = _benchmark_item(benchmark)
    return BenchmarkDetail(**item.model_dump(), submitter=benchmark.submitter)


@router.get("/{slug}/activity", response_model=list[AuditEventResponse])
async def get_benchmark_activity(
    slug: str,
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[AuditEventResponse]:
    benchmark = await session.scalar(select(Benchmark).where(Benchmark.slug == slug))
    if benchmark is None:
        raise AppError("benchmark_not_found", "Benchmark not found", status_code=404)
    events = list(
        (
            await session.scalars(
                select(AuditEvent)
                .options(selectinload(AuditEvent.actor))
                .where(AuditEvent.benchmark_id == benchmark.id)
                .order_by(AuditEvent.created_at.desc())
                .limit(limit)
            )
        ).all()
    )
    return [AuditEventResponse.model_validate(item) for item in events]
