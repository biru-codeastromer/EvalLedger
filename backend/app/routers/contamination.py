from __future__ import annotations

import json
from json import JSONDecodeError
from pathlib import Path
from typing import Annotated

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select

from app.config import get_settings
from app.dependencies import OptionalUser, SessionDep
from app.errors import AppError
from app.models.contamination import ReferenceCorpus
from app.ratelimit import RateLimit
from app.schemas.contamination import (
    ContaminationCheckResponse,
    ContaminationJobStatus,
    CorpusResponse,
)
from app.services.storage import StorageService
from app.tasks.contamination_tasks import celery_app, run_contamination_check
from app.utils.uploads import validate_upload_file

router = APIRouter()
settings = get_settings()
storage_service = StorageService.from_settings(settings)

_check_rl = Depends(RateLimit("contamination_check", anon_limit=10, auth_limit=20))


def _parse_corpus_ids(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    if raw_value.startswith("["):
        try:
            parsed = json.loads(raw_value)
        except JSONDecodeError as exc:
            raise AppError("invalid_corpora", "corpus_ids must be a valid JSON list", status_code=400) from exc
        if not isinstance(parsed, list):
            raise AppError("invalid_corpora", "corpus_ids must be a list of UUIDs", status_code=400)
        return [str(item) for item in parsed]
    return [item.strip() for item in raw_value.split(",") if item.strip()]


@router.get("/corpora", response_model=list[CorpusResponse])
async def list_corpora(session: SessionDep) -> list[CorpusResponse]:
    corpora = list(
        (
            await session.scalars(
                select(ReferenceCorpus).where(ReferenceCorpus.is_active.is_(True)).order_by(ReferenceCorpus.name)
            )
        ).all()
    )
    return [CorpusResponse.model_validate(corpus) for corpus in corpora]


@router.post("/check", response_model=ContaminationCheckResponse)
async def run_check(
    session: SessionDep,
    artifact: Annotated[UploadFile, File()],
    _rl: Annotated[None, _check_rl] = None,
    corpus_ids: Annotated[str | None, Form()] = None,
    current_user: OptionalUser = None,
) -> ContaminationCheckResponse:
    if not settings.worker_enabled:
        return ContaminationCheckResponse(
            job_id="",
            status="unavailable",
            filename=artifact.filename or "unknown",
            corpus_ids=[],
            message="Background processing is not available on the current deployment. "
            "Contamination checks require a Celery worker, which is not running.",
        )

    artifact_descriptor = validate_upload_file(artifact, authenticated=current_user is not None, settings=settings)
    file_bytes = await artifact.read()
    selected_ids = _parse_corpus_ids(corpus_ids)
    if not selected_ids:
        selected_ids = [
            str(item.id)
            for item in (
                await session.scalars(
                    select(ReferenceCorpus).where(ReferenceCorpus.is_active.is_(True)).order_by(ReferenceCorpus.name)
                )
            ).all()
        ]
    stored = await storage_service.upload_bytes(
        artifact_descriptor.filename,
        file_bytes,
        directory="checks/adhoc",
    )
    storage_reference = stored.artifact_url if settings.storage_backend == "local" else stored.storage_key
    task = run_contamination_check.delay(
        artifact_descriptor.filename or Path(storage_reference).name,
        storage_reference,
        selected_ids,
        None,
    )
    return ContaminationCheckResponse(
        job_id=task.id,
        status="queued",
        filename=artifact_descriptor.filename,
        corpus_ids=selected_ids,
    )


@router.get("/jobs/{job_id}", response_model=ContaminationJobStatus)
async def get_job_status(job_id: str) -> ContaminationJobStatus:
    if not settings.worker_enabled:
        return ContaminationJobStatus(
            job_id=job_id,
            status="unavailable",
            error="Background processing is not available on the current deployment.",
        )

    result = AsyncResult(job_id, app=celery_app)
    if result.failed():
        return ContaminationJobStatus(job_id=job_id, status="failed", error=str(result.result))
    if result.successful():
        return ContaminationJobStatus(job_id=job_id, status="completed", result=result.result)
    return ContaminationJobStatus(job_id=job_id, status=result.status.lower())
