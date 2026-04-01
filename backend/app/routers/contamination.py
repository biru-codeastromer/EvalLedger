from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from celery.result import AsyncResult
from fastapi import APIRouter, File, Form, UploadFile
from sqlalchemy import select

from app.config import get_settings
from app.dependencies import OptionalUser, SessionDep
from app.errors import AppError
from app.models.contamination import ReferenceCorpus
from app.schemas.contamination import (
    ContaminationCheckResponse,
    ContaminationJobStatus,
    CorpusResponse,
)
from app.services.storage import StorageService
from app.tasks.contamination_tasks import celery_app, run_contamination_check

router = APIRouter()
settings = get_settings()
storage_service = StorageService.from_settings(settings)


def _parse_corpus_ids(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    if raw_value.startswith("["):
        parsed = json.loads(raw_value)
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
    corpus_ids: Annotated[str | None, Form()] = None,
    current_user: OptionalUser = None,
) -> ContaminationCheckResponse:
    file_bytes = await artifact.read()
    if len(file_bytes) > settings.max_public_upload_bytes and current_user is None:
        raise AppError(
            "auth_required",
            "Authentication is required for uploads larger than 10MB",
            status_code=401,
        )
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
        artifact.filename or "check.bin",
        file_bytes,
        directory="checks/adhoc",
    )
    storage_reference = stored.artifact_url if settings.storage_backend == "local" else stored.storage_key
    task = run_contamination_check.delay(
        artifact.filename or Path(storage_reference).name,
        storage_reference,
        selected_ids,
        None,
    )
    return ContaminationCheckResponse(
        job_id=task.id,
        status="queued",
        filename=artifact.filename or "artifact",
        corpus_ids=selected_ids,
    )


@router.get("/jobs/{job_id}", response_model=ContaminationJobStatus)
async def get_job_status(job_id: str) -> ContaminationJobStatus:
    result = AsyncResult(job_id, app=celery_app)
    if result.failed():
        return ContaminationJobStatus(job_id=job_id, status="failed", error=str(result.result))
    if result.successful():
        return ContaminationJobStatus(job_id=job_id, status="completed", result=result.result)
    return ContaminationJobStatus(job_id=job_id, status=result.status.lower())
