"""OAuth account lookup and creation service.

Handles the find-or-create logic that maps an external OAuth identity to an
EvalLedger User, including safe account linking by verified email.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.models.user_identity import UserIdentity
from app.services.audit import record_audit_event

settings = get_settings()


def _is_admin_email(email: str) -> bool:
    return email.lower() in {e.lower() for e in settings.admin_emails}


def _slugify_username(raw: str) -> str:
    """Turn an arbitrary string into a valid username (3-32 chars, safe chars)."""
    cleaned = re.sub(r"[^a-z0-9_]", "", raw.lower())
    if not cleaned:
        cleaned = "user"
    return cleaned[:28]


async def _unique_username(session: AsyncSession, hint: str) -> str:
    """Return a username derived from *hint* that does not already exist."""
    base = _slugify_username(hint)
    # Try plain base name first.
    taken = await session.scalar(select(User).where(User.username == base))
    if taken is None:
        return base
    # Append incrementing numbers until we find a free slot.
    for i in range(1, 10_000):
        candidate = f"{base}{i}"[:32]
        taken = await session.scalar(select(User).where(User.username == candidate))
        if taken is None:
            return candidate
    # Extremely unlikely fallback.
    import uuid

    return f"{base[:20]}_{uuid.uuid4().hex[:8]}"


async def find_or_create_oauth_user(
    session: AsyncSession,
    *,
    provider: str,
    provider_user_id: str,
    email: str | None,
    display_name: str | None,
    username_hint: str,
) -> User:
    """Return the EvalLedger User for an authenticated OAuth identity.

    Strategy (in order):
    1. If we already have a ``UserIdentity`` for (provider, provider_user_id),
       return the linked user directly and update the stored email if it changed.
    2. If we have no identity but *email* matches an existing user, link the
       new identity to that account (account merging by verified email).
    3. Otherwise create a brand-new User + UserIdentity.

    The caller is responsible for committing the session.
    """
    # 1. Known identity?
    identity = await session.scalar(
        select(UserIdentity).where(
            UserIdentity.provider == provider,
            UserIdentity.provider_user_id == provider_user_id,
        )
    )
    if identity is not None:
        user = await session.scalar(select(User).where(User.id == identity.user_id))
        assert user is not None, "UserIdentity points to a missing user — data integrity error"
        # Keep the stored provider email up to date.
        if email and identity.provider_email != email:
            identity.provider_email = email
        # Sync admin status on every login (mirrors password-login behaviour).
        if email:
            expected_admin = _is_admin_email(email)
            if user.is_admin != expected_admin:
                user.is_admin = expected_admin
        return user

    # 2. Link by verified email if a matching user already exists.
    linked_user: User | None = None
    if email:
        linked_user = await session.scalar(select(User).where(User.email == email))

    # 3. Create a new user if not found by email.
    final_user: User
    if linked_user is not None:
        final_user = linked_user
    else:
        fallback_email = email or f"{provider}_{provider_user_id}@noreply.evalledger.app"
        username = await _unique_username(session, username_hint)
        new_user = User(
            email=fallback_email,
            username=username,
            password_hash=None,  # OAuth-only account — no password.
            display_name=display_name,
            is_admin=_is_admin_email(fallback_email),
        )
        session.add(new_user)
        await session.flush()
        await record_audit_event(
            session,
            action="user.registered",
            actor=new_user,
            resource_type="user",
            resource_id=str(new_user.id),
            resource_slug=new_user.username,
            summary=f"Created account via {provider} OAuth",
        )
        final_user = new_user

    # Create the identity record linking provider → user.
    new_identity = UserIdentity(
        user_id=final_user.id,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_email=email,
    )
    session.add(new_identity)
    return final_user
