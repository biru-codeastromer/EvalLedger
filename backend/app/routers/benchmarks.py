from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import load_only, selectinload

from app.dependencies import CurrentUser, SessionDep
from app.errors import AppError
from app.models.audit import AuditEvent
from app.models.benchmark import Benchmark
from app.models.user import User
from app.ratelimit import RateLimit
from app.schemas.audit import AuditEventResponse
from app.schemas.benchmark import (
    BenchmarkCreate,
    BenchmarkDetail,
    BenchmarkListItem,
    BenchmarkListResponse,
    BenchmarkUpdate,
)
from app.services.audit import record_audit_event
from app.services.query_projections import latest_version_projection

router = APIRouter()

_benchmark_logger = logging.getLogger("evalledger.benchmarks")
_benchmark_create_rl = Depends(RateLimit("benchmark_create", anon_limit=20, auth_limit=20))


def _benchmark_item(
    benchmark: Benchmark,
    *,
    latest_version: str | None = None,
    latest_contamination_status: str | None = None,
    latest_num_examples: int | None = None,
) -> BenchmarkListItem:
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
        latest_version=latest_version,
        latest_contamination_status=latest_contamination_status,
        latest_num_examples=latest_num_examples,
    )


@router.get("", response_model=BenchmarkListResponse)
async def list_benchmarks(
    session: SessionDep,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> BenchmarkListResponse:
    latest = latest_version_projection()
    total = await session.scalar(select(func.count(Benchmark.id)))
    rows = (
        await session.execute(
            select(
                Benchmark,
                latest.version,
                latest.contamination_status,
                latest.num_examples,
            )
            .order_by(Benchmark.created_at.desc(), Benchmark.slug)
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).all()
    return BenchmarkListResponse(
        page=page,
        limit=limit,
        total=total or 0,
        items=[
            _benchmark_item(
                row[0],
                latest_version=row.latest_version,
                latest_contamination_status=row.latest_contamination_status,
                latest_num_examples=row.latest_num_examples,
            )
            for row in rows
        ],
    )


@router.get("/{slug}", response_model=BenchmarkDetail)
async def get_benchmark(slug: str, session: SessionDep) -> BenchmarkDetail:
    latest = latest_version_projection()
    row = (
        await session.execute(
            select(
                Benchmark,
                latest.version,
                latest.contamination_status,
                latest.num_examples,
            )
            .options(selectinload(Benchmark.submitter))
            .where(Benchmark.slug == slug)
        )
    ).first()
    if row is None:
        raise AppError("benchmark_not_found", "Benchmark not found", status_code=404)
    benchmark = row[0]
    item = _benchmark_item(
        benchmark,
        latest_version=row.latest_version,
        latest_contamination_status=row.latest_contamination_status,
        latest_num_examples=row.latest_num_examples,
    )
    return BenchmarkDetail(**item.model_dump(), submitter=benchmark.submitter)


@router.post("", response_model=BenchmarkDetail, status_code=status.HTTP_201_CREATED)
async def create_benchmark(
    payload: BenchmarkCreate,
    session: SessionDep,
    current_user: CurrentUser,
    _rl: Annotated[None, _benchmark_create_rl] = None,
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
        .options(selectinload(Benchmark.submitter))
        .where(Benchmark.id == benchmark.id)
    )
    assert created is not None
    _benchmark_logger.info(
        "benchmark.created",
        extra={"benchmark_slug": benchmark.slug, "user_id": str(current_user.id)},
    )
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
        .options(selectinload(Benchmark.submitter))
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
    latest = latest_version_projection()
    row = (
        await session.execute(
            select(
                Benchmark,
                latest.version,
                latest.contamination_status,
                latest.num_examples,
            )
            .options(selectinload(Benchmark.submitter))
            .where(Benchmark.id == benchmark.id)
        )
    ).first()
    assert row is not None
    refreshed = row[0]
    item = _benchmark_item(
        refreshed,
        latest_version=row.latest_version,
        latest_contamination_status=row.latest_contamination_status,
        latest_num_examples=row.latest_num_examples,
    )
    return BenchmarkDetail(**item.model_dump(), submitter=refreshed.submitter)


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
                .options(
                    load_only(
                        AuditEvent.id,
                        AuditEvent.action,
                        AuditEvent.resource_type,
                        AuditEvent.resource_id,
                        AuditEvent.resource_slug,
                        AuditEvent.summary,
                        AuditEvent.metadata_json,
                        AuditEvent.created_at,
                        AuditEvent.actor_user_id,
                    ),
                    selectinload(AuditEvent.actor).load_only(
                        User.id, User.username, User.display_name, User.affiliation, User.is_verified
                    ),
                )
                .where(AuditEvent.benchmark_id == benchmark.id)
                .order_by(AuditEvent.created_at.desc())
                .limit(limit)
            )
        ).all()
    )
    return [AuditEventResponse.model_validate(item) for item in events]
