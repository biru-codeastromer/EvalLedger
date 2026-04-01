from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.schemas.common import ORMModel, UserSummary


class AuditEventResponse(ORMModel):
    id: UUID
    action: str
    resource_type: str
    resource_id: str | None = None
    resource_slug: str | None = None
    summary: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    actor: UserSummary | None = None
