from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.schemas.common import ORMModel, PaginatedResponse, UserSummary


class BenchmarkCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(min_length=20, max_length=500)
    domain: list[str] = Field(default_factory=list)
    task_type: str


class BenchmarkUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, min_length=20, max_length=500)
    domain: list[str] | None = None
    task_type: str | None = None
    website: HttpUrl | None = None


class BenchmarkListItem(ORMModel):
    id: UUID
    slug: str
    name: str
    description: str | None
    domain: list[str]
    task_type: str | None
    is_verified: bool
    total_versions: int
    total_citations: int
    created_at: datetime
    updated_at: datetime
    latest_version: str | None = None
    latest_contamination_status: str | None = None
    latest_num_examples: int | None = None


class BenchmarkDetail(BenchmarkListItem):
    submitter: UserSummary | None = None


class BenchmarkListResponse(PaginatedResponse):
    items: list[BenchmarkListItem]

