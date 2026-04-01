from __future__ import annotations

from datetime import UTC, datetime

import semver

from app.errors import AppError
from app.models.benchmark import Benchmark
from app.models.version import BenchmarkVersion


class VersioningService:
    def validate_semver(self, value: str) -> str:
        try:
            semver.Version.parse(value)
        except ValueError as exc:
            raise AppError("invalid_version", "Version must follow semantic versioning") from exc
        return value

    def canonical_id(self, slug: str, version: str) -> str:
        return f"el:{slug}:{version}"

    def citation_formats(self, benchmark: Benchmark, version: BenchmarkVersion) -> dict[str, str]:
        effective_timestamp = version.released_at or version.created_at or datetime.now(UTC)
        year = effective_timestamp.year
        canonical_id = self.canonical_id(benchmark.slug, version.version)
        title = benchmark.name.replace("{", "").replace("}", "")
        url = f"https://evalledger.dev/registry/{benchmark.slug}/{version.version}"
        sha_value = version.artifact_sha256 or "unavailable"
        bibtex_key = f"{benchmark.slug}_v{version.version.replace('.', '_')}"

        bibtex = (
            f"@dataset{{{bibtex_key},\n"
            f"  title    = {{{title}}},\n"
            f"  version  = {{{version.version}}},\n"
            f"  registry = {{EvalLedger}},\n"
            f"  id       = {{{canonical_id}}},\n"
            f"  sha256   = {{{sha_value}}},\n"
            f"  year     = {{{year}}},\n"
            f"  url      = {{{url}}}\n"
            f"}}"
        )
        apa = (
            f"{benchmark.name}. ({year}). EvalLedger registry entry {canonical_id} "
            f"(Version {version.version}). {url}"
        )
        mla = (
            f'"{benchmark.name}." EvalLedger, version {version.version}, {year}, '
            f"{url}. Registry ID {canonical_id}."
        )
        cff = "\n".join(
            [
                "cff-version: 1.2.0",
                'message: "If you use this benchmark, please cite it using the metadata below."',
                f'title: "{benchmark.name}"',
                f'version: "{version.version}"',
                'type: "dataset"',
                'publisher: "EvalLedger"',
                f'abstract: "{(benchmark.description or "").replace(chr(34), chr(39))}"',
                f'date-released: "{effective_timestamp.date().isoformat()}"',
                f'identifiers:\n  - type: "other"\n    value: "{canonical_id}"',
                f'url: "{url}"',
            ]
        )
        return {
            "bibtex": bibtex,
            "apa": apa,
            "mla": mla,
            "cff": cff,
            "evalledger_id": canonical_id,
        }

    def apply_citation_string(self, benchmark: Benchmark, version: BenchmarkVersion) -> None:
        version.citation_string = self.citation_formats(benchmark, version)["bibtex"]
