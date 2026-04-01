from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.schemas.common import ORMModel, UserSummary


class VersionCreate(BaseModel):
    version: str
    num_examples: int | None = Field(default=None, ge=0)
    splits: dict[str, int] | None = None
    language: list[str] | None = None
    license: str | None = None
    paper_url: HttpUrl | None = None
    paper_arxiv_id: str | None = None
    github_url: HttpUrl | None = None
    metadata: dict[str, Any] | None = None
    release_notes: str | None = None
    released_at: date | None = None


class CitationFormats(BaseModel):
    bibtex: str
    apa: str
    mla: str
    cff: str
    evalledger_id: str


class VersionListItem(ORMModel):
    id: UUID
    version: str
    artifact_sha256: str | None = None
    artifact_size_bytes: int | None = None
    num_examples: int | None = None
    contamination_status: str
    released_at: datetime | None = None
    created_at: datetime


class VersionDetail(VersionListItem):
    benchmark_id: UUID
    artifact_url: str | None = None
    splits: dict[str, Any] | None = None
    language: list[str] | None = None
    license: str | None = None
    paper_url: str | None = None
    paper_arxiv_id: str | None = None
    github_url: str | None = None
    release_notes: str | None = None
    metadata: dict[str, Any] | None = None
    submitter: UserSummary | None = None
    citations: CitationFormats


class VersionCreateResponse(BaseModel):
    benchmark_slug: str
    version: VersionDetail
    canonical_id: str
    contamination_job_ids: list[str]

