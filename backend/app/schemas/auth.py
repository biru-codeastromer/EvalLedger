from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.audit import AuditEventResponse
from app.schemas.common import ORMModel


class AuthUserResponse(ORMModel):
    id: UUID
    email: EmailStr
    username: str
    display_name: str | None = None
    affiliation: str | None = None
    is_verified: bool
    is_admin: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserResponse


class APIKeyCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class APIKeyResponse(ORMModel):
    id: UUID
    name: str | None
    last_used_at: datetime | None
    created_at: datetime
    is_active: bool


class APIKeyCreateResponse(BaseModel):
    api_key: str
    metadata: APIKeyResponse


class OwnedBenchmarkResponse(ORMModel):
    id: UUID
    slug: str
    name: str
    total_versions: int
    is_verified: bool
    updated_at: datetime


class MeResponse(BaseModel):
    user: AuthUserResponse
    api_keys: list[APIKeyResponse]
    benchmarks: list[OwnedBenchmarkResponse]
    recent_activity: list[AuditEventResponse]
