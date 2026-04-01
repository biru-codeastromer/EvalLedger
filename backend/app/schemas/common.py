from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse(BaseModel):
    page: int
    limit: int
    total: int


class UserSummary(ORMModel):
    id: UUID
    username: str
    display_name: str | None = None
    affiliation: str | None = None
    is_verified: bool


class VersionSummaryBase(ORMModel):
    id: UUID
    version: str
    contamination_status: str
    released_at: datetime | None = None
    created_at: datetime

