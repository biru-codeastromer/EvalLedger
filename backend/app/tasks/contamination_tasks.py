from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded

from app.config import get_settings
from app.database import SessionLocal
from app.logging import logger
from app.models.version import BenchmarkVersion
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
# Reliability: redeliver in-flight jobs if a worker crashes, process one job at a
# time, and bound how long any single job may run so a malformed or huge artifact
# cannot pin a worker slot forever.
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_soft_time_limit = settings.contamination_task_soft_time_limit
celery_app.conf.task_time_limit = settings.contamination_task_time_limit


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


async def _mark_version_error(version_id: str) -> None:
    """Best-effort: record that contamination checking failed for a version."""
    async with SessionLocal() as session:
        version = await session.get(BenchmarkVersion, UUID(version_id))
        if version is not None:
            version.contamination_status = "error"
            await session.commit()


@celery_app.task(
    bind=True,
    name="contamination.check",
    max_retries=3,
    autoretry_for=(ConnectionError, TimeoutError, OSError),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
)
def run_contamination_check(
    self: Any,
    artifact_name: str,
    artifact_location: str,
    corpus_ids: list[str],
    version_id: str | None = None,
) -> dict[str, Any]:
    try:
        return asyncio.run(_run_job(artifact_name, artifact_location, corpus_ids, version_id))
    except (ConnectionError, TimeoutError, OSError):
        # Transient infrastructure errors — let autoretry_for handle the backoff.
        raise
    except SoftTimeLimitExceeded:
        logger.error("contamination.job.timeout", extra={"version_id": version_id})
        if version_id is not None:
            asyncio.run(_mark_version_error(version_id))
        raise
    except Exception:
        # Permanent failure (e.g. a malformed artifact): surface an 'error' status
        # on the version instead of leaving it stuck on 'pending' forever.
        logger.exception("contamination.job.failed", extra={"version_id": version_id})
        if version_id is not None:
            asyncio.run(_mark_version_error(version_id))
        raise
