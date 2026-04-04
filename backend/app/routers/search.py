from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select

from app.dependencies import SessionDep
from app.models.benchmark import Benchmark
from app.ratelimit import RateLimit
from app.schemas.benchmark import BenchmarkListItem, BenchmarkListResponse
from app.services.query_projections import latest_version_projection

router = APIRouter()

SearchTerm = Annotated[str, Query()]
DomainFilter = Annotated[list[str] | None, Query()]
TaskTypeFilter = Annotated[str | None, Query()]
StatusFilter = Annotated[str | None, Query()]
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]

_search_rl = Depends(RateLimit("search", anon_limit=60, auth_limit=120))

@router.get("/search", response_model=BenchmarkListResponse)
async def search_benchmarks(
    session: SessionDep,
    _rl: Annotated[None, _search_rl] = None,
    q: SearchTerm = "",
    domain: DomainFilter = None,
    task_type: TaskTypeFilter = None,
    contamination_status: StatusFilter = None,
    page: PageNumber = 1,
    limit: PageSize = 20,
) -> BenchmarkListResponse:
    latest = latest_version_projection()
    base_statement = select(Benchmark.id).select_from(Benchmark)
    statement = select(
        Benchmark.id,
        Benchmark.slug,
        Benchmark.name,
        Benchmark.description,
        Benchmark.domain,
        Benchmark.task_type,
        Benchmark.is_verified,
        Benchmark.total_versions,
        Benchmark.total_citations,
        Benchmark.created_at,
        Benchmark.updated_at,
        latest.version,
        latest.contamination_status,
        latest.num_examples,
    ).select_from(Benchmark)
    if q:
        predicate = or_(
            Benchmark.search_vector.op("@@")(func.websearch_to_tsquery("english", q)),
            Benchmark.name.ilike(f"%{q}%"),
            Benchmark.description.ilike(f"%{q}%"),
        )
        statement = statement.where(predicate)
        base_statement = base_statement.where(predicate)
    if domain:
        statement = statement.where(Benchmark.domain.op("&&")(domain))
        base_statement = base_statement.where(Benchmark.domain.op("&&")(domain))
    if task_type:
        statement = statement.where(Benchmark.task_type == task_type)
        base_statement = base_statement.where(Benchmark.task_type == task_type)
    if contamination_status:
        statement = statement.where(latest.contamination_status == contamination_status)
        base_statement = base_statement.where(latest.contamination_status == contamination_status)
    total = (await session.scalar(select(func.count()).select_from(base_statement.subquery()))) or 0
    rows = (
        await session.execute(
            statement.order_by(Benchmark.name, Benchmark.slug)
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).all()
    return BenchmarkListResponse(
        page=page,
        limit=limit,
        total=total,
        items=[BenchmarkListItem(**dict(row._mapping)) for row in rows],
    )
