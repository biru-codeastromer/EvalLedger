from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.dependencies import SessionDep
from app.models.benchmark import Benchmark
from app.schemas.benchmark import BenchmarkListItem, BenchmarkListResponse

router = APIRouter()

SearchTerm = Annotated[str, Query()]
DomainFilter = Annotated[list[str] | None, Query()]
TaskTypeFilter = Annotated[str | None, Query()]
StatusFilter = Annotated[str | None, Query()]
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def _build_item(benchmark: Benchmark) -> BenchmarkListItem:
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


@router.get("/search", response_model=BenchmarkListResponse)
async def search_benchmarks(
    session: SessionDep,
    q: SearchTerm = "",
    domain: DomainFilter = None,
    task_type: TaskTypeFilter = None,
    contamination_status: StatusFilter = None,
    page: PageNumber = 1,
    limit: PageSize = 20,
) -> BenchmarkListResponse:
    statement = select(Benchmark).options(selectinload(Benchmark.versions))
    if q:
        statement = statement.where(
            or_(
                Benchmark.search_vector.op("@@")(func.websearch_to_tsquery("english", q)),
                Benchmark.name.ilike(f"%{q}%"),
                Benchmark.description.ilike(f"%{q}%"),
            )
        )
    if domain:
        statement = statement.where(Benchmark.domain.op("&&")(domain))
    if task_type:
        statement = statement.where(Benchmark.task_type == task_type)
    benchmarks = list((await session.scalars(statement.order_by(Benchmark.name))).all())
    if contamination_status:
        benchmarks = [
            benchmark
            for benchmark in benchmarks
            if benchmark.versions and benchmark.versions[0].contamination_status == contamination_status
        ]
    total = len(benchmarks)
    sliced = benchmarks[(page - 1) * limit : page * limit]
    return BenchmarkListResponse(
        page=page,
        limit=limit,
        total=total,
        items=[_build_item(item) for item in sliced],
    )
