from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.benchmark import Benchmark
from app.models.user_identity import UserIdentity  # noqa: F401
from app.routers import benchmarks as benchmarks_router
from app.routers import search as search_router
from app.scripts import loadtest


class ResultList:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class MappingRow:
    def __init__(self, **values):
        self._mapping = values


class BenchmarkRow:
    def __init__(self, benchmark: Benchmark, **values):
        self._benchmark = benchmark
        for key, value in values.items():
            setattr(self, key, value)

    def __getitem__(self, index: int):
        if index == 0:
            return self._benchmark
        raise IndexError(index)


class FakeSession:
    def __init__(self, *, scalar_value=None, execute_rows=None):
        self.scalar_value = scalar_value
        self.execute_rows = execute_rows or []

    async def scalar(self, _stmt):
        return self.scalar_value

    async def execute(self, _stmt):
        return ResultList(self.execute_rows)


def _make_benchmark() -> Benchmark:
    benchmark = Benchmark(
        id=uuid4(),
        slug="mmlu",
        name="MMLU",
        description="Massive multitask benchmark for performance regression tests.",
        domain=["reasoning"],
        task_type="multiple_choice",
        is_verified=True,
        total_versions=2,
        total_citations=3,
    )
    benchmark.created_at = datetime.now(UTC)
    benchmark.updated_at = datetime.now(UTC)
    return benchmark


def test_build_targets_requires_api_key_for_account_scenario() -> None:
    with pytest.raises(ValueError, match="api-key"):
        loadtest.build_targets(api_url="http://localhost:8000", scenario="account")


def test_build_targets_mixed_adds_admin_targets_when_api_key_present() -> None:
    targets = loadtest.build_targets(
        api_url="http://localhost:8000",
        scenario="mixed",
        api_key="secret",
    )
    names = [target.name for target in targets]
    assert "search_mmlu" in names
    assert "auth_me" in names
    assert "admin_review_queue" in names


def test_summarize_samples_groups_per_target() -> None:
    samples = [
        loadtest.RequestSample(target="search_mmlu", status_code=200, duration_ms=10.0),
        loadtest.RequestSample(target="search_mmlu", status_code=200, duration_ms=20.0),
        loadtest.RequestSample(target="benchmark_detail", status_code=None, duration_ms=5.0, error="timeout"),
    ]

    summary = loadtest.summarize_samples(samples, total_elapsed_ms=100.0)

    assert summary["requests"] == 3
    assert summary["successes"] == 2
    assert summary["failures"] == 1
    assert summary["targets"]["search_mmlu"]["requests"] == 2
    assert summary["targets"]["benchmark_detail"]["failures"] == 1


@pytest.mark.asyncio
async def test_search_benchmarks_uses_database_total_and_row_projection() -> None:
    session = FakeSession(
        scalar_value=42,
        execute_rows=[
            MappingRow(
                id=uuid4(),
                slug="mmlu",
                name="MMLU",
                description="Massive multitask benchmark.",
                domain=["reasoning"],
                task_type="multiple_choice",
                is_verified=True,
                total_versions=1,
                total_citations=2,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                latest_version="0.0.0",
                latest_contamination_status="clean",
                latest_num_examples=100,
            )
        ],
    )

    response = await search_router.search_benchmarks(
        session=session,
        q="mmlu",
        page=2,
        limit=1,
    )

    assert response.total == 42
    assert len(response.items) == 1
    assert response.items[0].latest_version == "0.0.0"
    assert response.items[0].latest_contamination_status == "clean"


@pytest.mark.asyncio
async def test_list_benchmarks_uses_latest_projection_fields() -> None:
    benchmark = _make_benchmark()
    session = FakeSession(
        scalar_value=7,
        execute_rows=[
            BenchmarkRow(
                benchmark,
                latest_version="1.1.0",
                latest_contamination_status="unchecked",
                latest_num_examples=512,
            )
        ],
    )

    response = await benchmarks_router.list_benchmarks(session=session, page=1, limit=20)

    assert response.total == 7
    assert len(response.items) == 1
    assert response.items[0].slug == "mmlu"
    assert response.items[0].latest_version == "1.1.0"
    assert response.items[0].latest_num_examples == 512
