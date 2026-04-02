"""Auth router — session info and API key management.

Email/password registration and login have been retired.  Authentication is
now performed exclusively via GitHub or Google OAuth (see routers/oauth.py).
This router handles everything that happens *after* a session is established:
inspecting the current user profile, minting API keys, and revoking them.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import CurrentUser, SessionDep
from app.errors import AppError
from app.models.api_key import APIKey
from app.models.audit import AuditEvent
from app.models.benchmark import Benchmark
from app.schemas.audit import AuditEventResponse
from app.schemas.auth import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyResponse,
    MeResponse,
    OwnedBenchmarkResponse,
)
from app.security import (
    generate_api_key,
    hash_api_key,
)
from app.services.audit import record_audit_event

router = APIRouter()


def _auth_user_payload(user: object) -> dict[str, object]:
    from app.models.user import User

    assert isinstance(user, User)
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "display_name": user.display_name,
        "affiliation": user.affiliation,
        "is_verified": user.is_verified,
        "is_admin": user.is_admin,
    }


@router.post("/api-keys", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: APIKeyCreateRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> APIKeyCreateResponse:
    plain_key = generate_api_key()
    api_key = APIKey(user_id=current_user.id, name=payload.name, key_hash=hash_api_key(plain_key))
    session.add(api_key)
    await session.flush()
    await record_audit_event(
        session,
        action="api_key.created",
        actor=current_user,
        resource_type="api_key",
        resource_id=str(api_key.id),
        resource_slug=payload.name,
        summary=f"Created API key {payload.name}",
    )
    await session.commit()
    await session.refresh(api_key)
    return APIKeyCreateResponse(api_key=plain_key, metadata=APIKeyResponse.model_validate(api_key))


@router.delete("/api-keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_api_key(api_key_id: str, session: SessionDep, current_user: CurrentUser) -> None:
    api_key = await session.scalar(select(APIKey).where(APIKey.id == api_key_id, APIKey.user_id == current_user.id))
    if api_key is None:
        raise AppError("api_key_not_found", "API key does not exist", status_code=404)
    api_key.is_active = False
    await record_audit_event(
        session,
        action="api_key.revoked",
        actor=current_user,
        resource_type="api_key",
        resource_id=str(api_key.id),
        resource_slug=api_key.name,
        summary=f"Revoked API key {api_key.name or api_key.id}",
    )
    await session.commit()


@router.get("/me", response_model=MeResponse)
async def me(session: SessionDep, current_user: CurrentUser) -> MeResponse:
    api_keys = list(
        (
            await session.scalars(
                select(APIKey).where(APIKey.user_id == current_user.id).order_by(APIKey.created_at.desc())
            )
        ).all()
    )
    benchmarks = list(
        (
            await session.scalars(
                select(Benchmark)
                .where(Benchmark.submitter_id == current_user.id)
                .order_by(Benchmark.updated_at.desc(), Benchmark.created_at.desc())
            )
        ).all()
    )
    activity = list(
        (
            await session.scalars(
                select(AuditEvent)
                .options(selectinload(AuditEvent.actor))
                .where(AuditEvent.actor_user_id == current_user.id)
                .order_by(AuditEvent.created_at.desc())
                .limit(20)
            )
        ).all()
    )
    return MeResponse(
        user=_auth_user_payload(current_user),
        api_keys=[APIKeyResponse.model_validate(item) for item in api_keys],
        benchmarks=[OwnedBenchmarkResponse.model_validate(item) for item in benchmarks],
        recent_activity=[AuditEventResponse.model_validate(item) for item in activity],
    )
