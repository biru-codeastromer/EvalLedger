from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel, UserSummary


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = None
    bio: str | None = None
    website: str | None = None
    affiliation: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSummary


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

