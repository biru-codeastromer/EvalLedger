from __future__ import annotations

import asyncio
from typing import Any

from celery import Celery

from app.config import get_settings
from app.database import SessionLocal
from app.services.contamination_engine import ContaminationEngine
from app.services.storage import StorageService

settings = get_settings()
celery_app = Celery(
    "evalledger",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.task_track_started = True
celery_app.conf.result_expires = 60 * 60 * 24


async def _run_job(
    artifact_name: str,
    artifact_location: str,
    corpus_ids: list[str],
    version_id: str | None,
) -> dict[str, Any]:
    async with SessionLocal() as session:
        engine = ContaminationEngine(session, StorageService.from_settings(settings))
        return await engine.run_detection(
            artifact_name=artifact_name,
            artifact_location=artifact_location,
            corpus_ids=corpus_ids,
            version_id=version_id,
        )


@celery_app.task(name="contamination.check")
def run_contamination_check(
    artifact_name: str,
    artifact_location: str,
    corpus_ids: list[str],
    version_id: str | None = None,
) -> dict[str, Any]:
    return asyncio.run(_run_job(artifact_name, artifact_location, corpus_ids, version_id))

