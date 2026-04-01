from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import ORMModel, PaginatedResponse


class CorpusResponse(ORMModel):
    id: UUID
    name: str
    description: str | None = None
    version: str | None = None
    size_tokens: int | None = None
    source_url: str | None = None
    is_active: bool


class ContaminationReportItem(ORMModel):
    id: UUID
    corpus_id: UUID
    status: str
    overlap_score: float | None = None
    num_flagged_examples: int | None = None
    flagged_examples: list[dict[str, Any]] | None = None
    minhash_threshold: float
    job_started_at: datetime | None = None
    job_completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    corpus_name: str | None = None


class ContaminationCheckResponse(BaseModel):
    job_id: str
    status: str
    filename: str
    corpus_ids: list[str]


class ContaminationJobStatus(BaseModel):
    job_id: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None


class RecentSubmissionsResponse(PaginatedResponse):
    items: list[dict[str, Any]]

