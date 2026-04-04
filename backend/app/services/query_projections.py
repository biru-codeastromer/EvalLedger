from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from app.models.benchmark import Benchmark
from app.models.version import BenchmarkVersion


@dataclass(frozen=True)
class LatestVersionProjection:
    version: Any
    contamination_status: Any
    num_examples: Any
    artifact_sha256: Any
    artifact_size_bytes: Any


def _latest_version_scalar(column: Any) -> Any:
    return (
        select(column)
        .where(BenchmarkVersion.benchmark_id == Benchmark.id)
        .order_by(BenchmarkVersion.created_at.desc())
        .limit(1)
        .correlate(Benchmark)
        .scalar_subquery()
    )


def latest_version_projection() -> LatestVersionProjection:
    return LatestVersionProjection(
        version=_latest_version_scalar(BenchmarkVersion.version).label("latest_version"),
        contamination_status=_latest_version_scalar(BenchmarkVersion.contamination_status).label(
            "latest_contamination_status"
        ),
        num_examples=_latest_version_scalar(BenchmarkVersion.num_examples).label("latest_num_examples"),
        artifact_sha256=_latest_version_scalar(BenchmarkVersion.artifact_sha256).label(
            "latest_artifact_sha256"
        ),
        artifact_size_bytes=_latest_version_scalar(BenchmarkVersion.artifact_size_bytes).label(
            "latest_artifact_size_bytes"
        ),
    )
