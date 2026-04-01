from __future__ import annotations

from dataclasses import dataclass

from app.models.benchmark import Benchmark
from app.models.version import BenchmarkVersion


@dataclass(slots=True)
class ProvenanceSummary:
    benchmark_name: str
    benchmark_slug: str
    version: str
    artifact_sha256: str | None
    artifact_size_bytes: int | None
    contamination_status: str
    canonical_id: str


def build_provenance_summary(
    benchmark: Benchmark, version: BenchmarkVersion, canonical_id: str
) -> ProvenanceSummary:
    return ProvenanceSummary(
        benchmark_name=benchmark.name,
        benchmark_slug=benchmark.slug,
        version=version.version,
        artifact_sha256=version.artifact_sha256,
        artifact_size_bytes=version.artifact_size_bytes,
        contamination_status=version.contamination_status,
        canonical_id=canonical_id,
    )

