"""Account lifecycle service: GDPR data export and erasure.

Erasure is a *soft delete with anonymization*: the User row is retained so the
immutable audit trail and benchmark/version foreign keys stay valid, but every
piece of personal data is overwritten, API keys are revoked, and OAuth identity
links are removed. ``deleted_at`` is stamped so authentication rejects the
account thereafter.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import APIKey
from app.models.audit import AuditEvent
from app.models.benchmark import Benchmark
from app.models.user import User
from app.models.user_identity import UserIdentity
from app.models.version import BenchmarkVersion
from app.services.audit import record_audit_event


async def export_user_data(session: AsyncSession, user: User) -> dict[str, Any]:
    """Return a JSON-serialisable copy of everything tied to *user* (GDPR Art. 15/20)."""
    identities = (await session.scalars(select(UserIdentity).where(UserIdentity.user_id == user.id))).all()
    api_keys = (await session.scalars(select(APIKey).where(APIKey.user_id == user.id))).all()
    benchmarks = (await session.scalars(select(Benchmark).where(Benchmark.submitter_id == user.id))).all()
    versions = (await session.scalars(select(BenchmarkVersion).where(BenchmarkVersion.submitter_id == user.id))).all()
    audit_events = (
        await session.scalars(
            select(AuditEvent).where(AuditEvent.actor_user_id == user.id).order_by(AuditEvent.created_at.desc())
        )
    ).all()

    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "profile": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "display_name": user.display_name,
            "bio": user.bio,
            "website": user.website,
            "affiliation": user.affiliation,
            "is_verified": user.is_verified,
            "is_admin": user.is_admin,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "oauth_identities": [
            {"provider": i.provider, "provider_email": i.provider_email} for i in identities
        ],
        "api_keys": [
            {"id": str(k.id), "name": k.name, "is_active": k.is_active,
             "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None}
            for k in api_keys
        ],
        "benchmarks": [{"slug": b.slug, "name": b.name} for b in benchmarks],
        "versions": [{"benchmark_id": str(v.benchmark_id), "version": v.version} for v in versions],
        "audit_events": [
            {"action": e.action, "resource_type": e.resource_type, "resource_slug": e.resource_slug,
             "summary": e.summary, "created_at": e.created_at.isoformat() if e.created_at else None}
            for e in audit_events
        ],
    }


async def delete_user(session: AsyncSession, user: User) -> None:
    """Anonymize *user* in place, revoke keys, unlink OAuth identities, stamp deleted_at.

    The caller is responsible for committing the session.
    """
    user_id = user.id
    # Overwrite personal data. The email/username tombstones embed the id so
    # they never collide with the unique constraints on those columns.
    user.email = f"deleted-{user_id}@deleted.evalledger.app"
    user.username = f"deleted_{uuid4().hex[:16]}"
    user.display_name = None
    user.bio = None
    user.website = None
    user.affiliation = None
    user.password_hash = None
    user.is_admin = False
    user.is_verified = False
    user.deleted_at = datetime.now(UTC)

    for key in (await session.scalars(select(APIKey).where(APIKey.user_id == user_id))).all():
        key.is_active = False
    for identity in (await session.scalars(select(UserIdentity).where(UserIdentity.user_id == user_id))).all():
        await session.delete(identity)

    await record_audit_event(
        session,
        action="user.deleted",
        actor=user,
        resource_type="user",
        resource_id=str(user_id),
        resource_slug=None,
        summary="Account erased at user request (GDPR)",
    )
