from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.dependencies import OptionalUser, SessionDep
from app.errors import AppError
from app.models.benchmark import Benchmark
from app.models.contamination import ContaminationReport, ReferenceCorpus
from app.models.version import BenchmarkVersion
from app.schemas.contamination import ContaminationReportItem
from app.schemas.version import (
    CitationFormats,
    VersionCreateResponse,
    VersionDetail,
    VersionListItem,
)
from app.services.storage import StorageService
from app.services.versioning import VersioningService
from app.tasks.contamination_tasks import run_contamination_check

router = APIRouter()
settings = get_settings()
storage_service = StorageService.from_settings(settings)
versioning_service = VersioningService()
CitationFormatQuery = Annotated[str | None, Query()]


def _parse_json_field(raw_value: str | None) -> dict[str, Any] | None:
    if raw_value is None or not raw_value.strip():
        return None
    payload = json.loads(raw_value)
    if not isinstance(payload, dict):
        raise AppError("invalid_metadata", "Expected a JSON object payload", status_code=400)
    return payload


def _parse_language_field(raw_value: str | None) -> list[str] | None:
    if raw_value is None or not raw_value.strip():
        return None
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _build_version_detail(benchmark: Benchmark, version: BenchmarkVersion) -> VersionDetail:
    citations = versioning_service.citation_formats(benchmark, version)
    return VersionDetail(
        id=version.id,
        benchmark_id=benchmark.id,
        version=version.version,
        artifact_sha256=version.artifact_sha256,
        artifact_url=version.artifact_url,
        artifact_size_bytes=version.artifact_size_bytes,
        num_examples=version.num_examples,
        splits=version.splits,
        language=version.language,
        license=version.license,
        paper_url=version.paper_url,
        paper_arxiv_id=version.paper_arxiv_id,
        github_url=version.github_url,
        release_notes=version.release_notes,
        metadata=version.metadata_json,
        contamination_status=version.contamination_status,
        released_at=version.released_at,
        created_at=version.created_at,
        submitter=version.submitter,
        citations=CitationFormats(**citations),
    )


async def _fetch_benchmark(session: SessionDep, slug: str) -> Benchmark:
    benchmark = await session.scalar(
        select(Benchmark)
        .options(selectinload(Benchmark.versions), selectinload(Benchmark.submitter))
        .where(Benchmark.slug == slug)
    )
    if benchmark is None:
        raise AppError("benchmark_not_found", "Benchmark not found", status_code=404)
    return benchmark


@router.get("/{slug}/versions", response_model=list[VersionListItem])
async def list_versions(slug: str, session: SessionDep) -> list[VersionListItem]:
    benchmark = await _fetch_benchmark(session, slug)
    return [VersionListItem.model_validate(version) for version in benchmark.versions]


@router.post("/{slug}/versions", response_model=VersionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_version(
    slug: str,
    session: SessionDep,
    artifact: Annotated[UploadFile, File()],
    version: Annotated[str, Form()],
    current_user: OptionalUser = None,
    num_examples: Annotated[int | None, Form()] = None,
    splits: Annotated[str | None, Form()] = None,
    language: Annotated[str | None, Form()] = None,
    license: Annotated[str | None, Form()] = None,
    paper_url: Annotated[str | None, Form()] = None,
    paper_arxiv_id: Annotated[str | None, Form()] = None,
    github_url: Annotated[str | None, Form()] = None,
    metadata: Annotated[str | None, Form()] = None,
    release_notes: Annotated[str | None, Form()] = None,
    released_at: Annotated[str | None, Form()] = None,
) -> VersionCreateResponse:
    benchmark = await _fetch_benchmark(session, slug)
    versioning_service.validate_semver(version)
    existing = await session.scalar(
        select(BenchmarkVersion).where(
            BenchmarkVersion.benchmark_id == benchmark.id,
            BenchmarkVersion.version == version,
        )
    )
    if existing is not None:
        raise AppError("version_exists", "That version already exists", status_code=409)

    stored = await storage_service.upload_upload_file(
        artifact.filename or "artifact.bin",
        artifact.file,
        directory=f"benchmarks/{benchmark.slug}",
    )
    storage_reference = stored.artifact_url if settings.storage_backend == "local" else stored.storage_key
    version_record = BenchmarkVersion(
        benchmark_id=benchmark.id,
        version=version,
        artifact_sha256=stored.sha256,
        artifact_url=storage_reference,
        artifact_size_bytes=stored.size_bytes,
        num_examples=num_examples,
        splits=_parse_json_field(splits),
        language=_parse_language_field(language),
        license=license,
        paper_url=paper_url,
        paper_arxiv_id=paper_arxiv_id,
        github_url=github_url,
        metadata_json=_parse_json_field(metadata),
        release_notes=release_notes,
        released_at=datetime.fromisoformat(released_at) if released_at else None,
        submitter_id=current_user.id if current_user else None,
        contamination_status="pending",
    )
    versioning_service.apply_citation_string(benchmark, version_record)
    session.add(version_record)
    benchmark.total_versions = benchmark.total_versions + 1
    await session.commit()
    await session.refresh(version_record)
    await session.refresh(benchmark)

    corpus_ids = [
        str(corpus.id)
        for corpus in (
            await session.scalars(
                select(ReferenceCorpus).where(ReferenceCorpus.is_active.is_(True)).order_by(ReferenceCorpus.name)
            )
        ).all()
    ]
    task = run_contamination_check.delay(
        artifact.filename or Path(storage_reference).name,
        storage_reference,
        corpus_ids,
        str(version_record.id),
    )
    detail = _build_version_detail(benchmark, version_record)
    return VersionCreateResponse(
        benchmark_slug=benchmark.slug,
        version=detail,
        canonical_id=versioning_service.canonical_id(benchmark.slug, version_record.version),
        contamination_job_ids=[task.id],
    )


@router.get("/{slug}/{version}/download", response_model=None)
async def download_version(
    slug: str,
    version: str,
    session: SessionDep,
) -> FileResponse | RedirectResponse:
    benchmark = await _fetch_benchmark(session, slug)
    version_record = await session.scalar(
        select(BenchmarkVersion).where(
            BenchmarkVersion.benchmark_id == benchmark.id,
            BenchmarkVersion.version == version,
        )
    )
    if version_record is None or version_record.artifact_url is None:
        raise AppError("artifact_missing", "Artifact is not available for download", status_code=404)
    download_url = await storage_service.generate_download_url(version_record.artifact_url)
    if settings.storage_backend == "local":
        return FileResponse(download_url, filename=f"{benchmark.slug}-{version}.bin")
    return RedirectResponse(download_url)


@router.get("/{slug}/{version}/contamination", response_model=list[ContaminationReportItem])
async def get_contamination_reports(slug: str, version: str, session: SessionDep) -> list[ContaminationReportItem]:
    benchmark = await _fetch_benchmark(session, slug)
    version_record = await session.scalar(
        select(BenchmarkVersion)
        .options(selectinload(BenchmarkVersion.contamination_reports))
        .where(BenchmarkVersion.benchmark_id == benchmark.id, BenchmarkVersion.version == version)
    )
    if version_record is None:
        raise AppError("version_not_found", "Version not found", status_code=404)

    reports = list(
        (
            await session.execute(
                select(ContaminationReport, ReferenceCorpus.name)
                .join(ReferenceCorpus, ReferenceCorpus.id == ContaminationReport.corpus_id)
                .where(ContaminationReport.version_id == version_record.id)
            )
        ).all()
    )
    return [
        ContaminationReportItem(
            id=report.id,
            corpus_id=report.corpus_id,
            corpus_name=corpus_name,
            status=report.status,
            overlap_score=report.overlap_score,
            num_flagged_examples=report.num_flagged_examples,
            flagged_examples=report.flagged_examples,
            minhash_threshold=report.minhash_threshold,
            job_started_at=report.job_started_at,
            job_completed_at=report.job_completed_at,
            error_message=report.error_message,
            created_at=report.created_at,
        )
        for report, corpus_name in reports
    ]


@router.get("/{slug}/{version}/citation", response_model=None)
async def get_citation(
    slug: str,
    version: str,
    session: SessionDep,
    format: CitationFormatQuery = None,
) -> dict[str, str] | PlainTextResponse:
    benchmark = await _fetch_benchmark(session, slug)
    version_record = await session.scalar(
        select(BenchmarkVersion).where(
            BenchmarkVersion.benchmark_id == benchmark.id,
            BenchmarkVersion.version == version,
        )
    )
    if version_record is None:
        raise AppError("version_not_found", "Version not found", status_code=404)
    citations = versioning_service.citation_formats(benchmark, version_record)
    if format:
        normalized = "cff" if format.lower() in {"citation.cff", "cff"} else format.lower()
        if normalized not in citations:
            raise AppError("invalid_format", "Unsupported citation format", status_code=400)
        return PlainTextResponse(citations[normalized])
    return citations


@router.get("/{slug}/{version}", response_model=VersionDetail)
async def get_version_detail(slug: str, version: str, session: SessionDep) -> VersionDetail:
    benchmark = await session.scalar(
        select(Benchmark)
        .options(
            selectinload(Benchmark.submitter),
            selectinload(Benchmark.versions).selectinload(BenchmarkVersion.submitter),
        )
        .where(Benchmark.slug == slug)
    )
    if benchmark is None:
        raise AppError("benchmark_not_found", "Benchmark not found", status_code=404)
    version_record = next((item for item in benchmark.versions if item.version == version), None)
    if version_record is None:
        raise AppError("version_not_found", "Version not found", status_code=404)
    return _build_version_detail(benchmark, version_record)
