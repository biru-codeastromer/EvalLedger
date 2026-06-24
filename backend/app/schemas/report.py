from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

ResourceType = Literal["benchmark", "version"]
ReportReason = Literal["malicious", "infringement", "mislabeled", "privacy", "other"]
ReportStatus = Literal["open", "reviewing", "actioned", "dismissed"]


class ReportCreateRequest(BaseModel):
    resource_type: ResourceType
    resource_slug: str = Field(min_length=1, max_length=300)
    reason: ReportReason
    detail: str | None = Field(default=None, max_length=4000)


class ReportResolveRequest(BaseModel):
    status: Literal["reviewing", "actioned", "dismissed"]
    resolution_note: str | None = Field(default=None, max_length=4000)


class ReportResponse(ORMModel):
    id: UUID
    reporter_user_id: UUID
    resource_type: str
    resource_slug: str
    reason: str
    detail: str | None
    status: str
    created_at: datetime
    resolved_at: datetime | None
    resolver_user_id: UUID | None
    resolution_note: str | None
