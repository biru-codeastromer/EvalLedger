"""Auth router — session info and API key management.

Email/password registration and login have been retired.  Authentication is
now performed exclusively via GitHub or Google OAuth (see routers/oauth.py).
This router handles everything that happens *after* a session is established:
inspecting the current user profile, minting API keys, and revoking them.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import load_only, selectinload

from app.dependencies import CurrentUser, SessionDep
from app.errors import AppError
from app.models.api_key import APIKey
from app.models.audit import AuditEvent
from app.models.benchmark import Benchmark
from app.models.user import User
from app.ratelimit import RateLimit
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

_auth_logger = logging.getLogger("evalledger.auth")

# Rate limit buckets for auth endpoints (all callers are authenticated here,
# so anon_limit == auth_limit keeps the logic simple).
_me_rl = Depends(RateLimit("auth_me", anon_limit=30, auth_limit=30))
_apikey_create_rl = Depends(RateLimit("auth_apikey_create", anon_limit=10, auth_limit=10))
_apikey_delete_rl = Depends(RateLimit("auth_apikey_delete", anon_limit=10, auth_limit=10))


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
    _rl: Annotated[None, _apikey_create_rl] = None,
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
    _auth_logger.info(
        "api_key.created",
        extra={"user_id": str(current_user.id), "key_name": payload.name},
    )
    return APIKeyCreateResponse(api_key=plain_key, metadata=APIKeyResponse.model_validate(api_key))


@router.delete("/api-keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_api_key(
    api_key_id: str,
    session: SessionDep,
    current_user: CurrentUser,
    _rl: Annotated[None, _apikey_delete_rl] = None,
) -> None:
    api_key = await session.scalar(select(APIKey).where(APIKey.id == api_key_id, APIKey.user_id == current_user.id))
    if api_key is None:
        raise AppError("api_key_not_found", "API key does not exist", status_code=404)
    api_key.is_active = False
    _auth_logger.info(
        "api_key.revoked",
        extra={"user_id": str(current_user.id), "key_id": api_key_id, "key_name": api_key.name},
    )
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
async def me(
    session: SessionDep,
    current_user: CurrentUser,
    _rl: Annotated[None, _me_rl] = None,
) -> MeResponse:
    api_keys = list(
        (
            await session.scalars(
                select(APIKey)
                .options(
                    load_only(
                        APIKey.id,
                        APIKey.name,
                        APIKey.last_used_at,
                        APIKey.created_at,
                        APIKey.is_active,
                    )
                )
                .where(APIKey.user_id == current_user.id)
                .order_by(APIKey.created_at.desc())
            )
        ).all()
    )
    benchmarks = list(
        (
            await session.scalars(
                select(Benchmark)
                .options(
                    load_only(
                        Benchmark.id,
                        Benchmark.slug,
                        Benchmark.name,
                        Benchmark.total_versions,
                        Benchmark.is_verified,
                        Benchmark.updated_at,
                    )
                )
                .where(Benchmark.submitter_id == current_user.id)
                .order_by(Benchmark.updated_at.desc(), Benchmark.created_at.desc())
            )
        ).all()
    )
    activity = list(
        (
            await session.scalars(
                select(AuditEvent)
                .options(
                    load_only(
                        AuditEvent.id,
                        AuditEvent.action,
                        AuditEvent.resource_type,
                        AuditEvent.resource_id,
                        AuditEvent.resource_slug,
                        AuditEvent.summary,
                        AuditEvent.metadata_json,
                        AuditEvent.created_at,
                        AuditEvent.actor_user_id,
                    ),
                    selectinload(AuditEvent.actor).load_only(
                        User.id,
                        User.username,
                        User.display_name,
                        User.affiliation,
                        User.is_verified,
                    ),
                )
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
