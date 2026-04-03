"""Tests for the OAuth callback flow and user creation/linking logic."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.routers import oauth as oauth_router
from app.security import create_access_token

# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def _make_fake_request() -> MagicMock:
    """Return a minimal mock Request sufficient for rate-limit and callback tests."""
    req = MagicMock()
    req.headers = {}
    client = MagicMock()
    client.host = "127.0.0.1"
    req.client = client
    return req


async def _passthrough_rate_limit(request: object, bucket: str) -> None:
    """Stub for _oauth_rate_limit that never throttles (returns None)."""
    return None


# ---------------------------------------------------------------------------
# State-token helpers
# ---------------------------------------------------------------------------


def test_state_token_roundtrip() -> None:
    """A freshly minted state token must decode correctly."""
    token = oauth_router._make_state_token()
    # Must not raise.
    oauth_router._verify_state_token(token)


def test_state_token_wrong_purpose_rejected() -> None:
    """A token with a non-oauth_state purpose must be rejected."""
    from app.errors import AppError

    bad_token = create_access_token("some_user_id")  # purpose claim absent
    with pytest.raises(AppError) as exc_info:
        oauth_router._verify_state_token(bad_token)
    assert exc_info.value.code == "invalid_oauth_state"


def test_state_token_expired_rejected() -> None:
    """An expired state token must be rejected."""
    import jwt

    from app.config import get_settings
    from app.errors import AppError

    s = get_settings()
    payload = {
        "sub": "oauth_state",
        "purpose": "oauth_state",
        "iat": 1_000_000,
        "exp": 1_000_001,  # well in the past
    }
    expired_token = jwt.encode(payload, s.jwt_secret_key, algorithm=s.jwt_algorithm)
    with pytest.raises(AppError):
        oauth_router._verify_state_token(expired_token)


# ---------------------------------------------------------------------------
# find_or_create_oauth_user — unit tests with fake session
# ---------------------------------------------------------------------------


class _FakeSession:
    """Minimal async SQLAlchemy session stub."""

    def __init__(self, existing_identity: object = None, existing_user: object = None) -> None:
        self._existing_identity = existing_identity
        self._existing_user = existing_user
        self.added: list[object] = []
        self.flushed = False
        self.committed = False

    async def scalar(self, _statement: object) -> object:
        # Return identity or user based on what was registered.

        if _statement is self._identity_stmt:
            return self._existing_identity
        if _statement is self._user_stmt:
            return self._existing_user
        return None

    # We abuse __class__ checks via monkeypatch below; keep simple.
    async def flush(self) -> None:
        self.flushed = True
        if self.added:
            for item in self.added:
                if not getattr(item, "id", None):
                    item.id = uuid4()  # type: ignore[union-attr]
                if not getattr(item, "created_at", None):
                    item.created_at = datetime.now(UTC)  # type: ignore[union-attr]

    def add(self, item: object) -> None:
        self.added.append(item)

    async def commit(self) -> None:
        self.committed = True

    _identity_stmt: object = None
    _user_stmt: object = None


@pytest.mark.asyncio
async def test_find_or_create_creates_new_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no identity and no email match exists, a new User + UserIdentity is created."""
    from app.models.user import User
    from app.models.user_identity import UserIdentity
    from app.services import oauth as svc

    # All DB lookups return None → new user path.
    fake_session = AsyncMock()
    fake_session.scalar.return_value = None
    fake_session.flush = AsyncMock()
    fake_session.add = MagicMock()

    # Patch record_audit_event to a no-op.
    monkeypatch.setattr(svc, "record_audit_event", AsyncMock())

    user = await svc.find_or_create_oauth_user(
        fake_session,  # type: ignore[arg-type]
        provider="github",
        provider_user_id="99999",
        email="alice@example.com",
        display_name="Alice",
        username_hint="alice",
    )

    assert isinstance(user, User)
    assert user.email == "alice@example.com"
    assert user.username == "alice"
    assert user.password_hash is None  # OAuth user — no password

    # Both User and UserIdentity must have been added.
    # call_args_list entries are Call objects; extract first positional arg.
    added_objects = [call.args[0] for call in fake_session.add.call_args_list]
    assert any(isinstance(obj, User) for obj in added_objects)
    assert any(isinstance(obj, UserIdentity) for obj in added_objects)


@pytest.mark.asyncio
async def test_find_or_create_links_existing_user_by_email(monkeypatch: pytest.MonkeyPatch) -> None:
    """When email matches an existing user, the identity is linked to that user."""
    from app.models.user import User
    from app.models.user_identity import UserIdentity
    from app.services import oauth as svc

    existing_user = User(
        id=uuid4(),
        email="bob@example.com",
        username="bob",
        password_hash="$2b$12$hash",
        is_admin=False,
        is_verified=True,
    )

    call_count = 0

    async def fake_scalar(_stmt: object) -> object:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return None  # no existing identity
        return existing_user  # email lookup returns existing user

    fake_session = AsyncMock()
    fake_session.scalar.side_effect = fake_scalar
    fake_session.flush = AsyncMock()
    fake_session.add = MagicMock()

    monkeypatch.setattr(svc, "record_audit_event", AsyncMock())

    user = await svc.find_or_create_oauth_user(
        fake_session,  # type: ignore[arg-type]
        provider="google",
        provider_user_id="google-sub-abc",
        email="bob@example.com",
        display_name="Bob",
        username_hint="bob",
    )

    # Must return the pre-existing user without creating a new one.
    assert user is existing_user
    # Only UserIdentity should have been added (no new User).
    added_objects = [call.args[0] for call in fake_session.add.call_args_list]
    assert not any(isinstance(obj, User) for obj in added_objects)
    assert any(isinstance(obj, UserIdentity) for obj in added_objects)


@pytest.mark.asyncio
async def test_find_or_create_returns_existing_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """When (provider, provider_user_id) is known, return the linked user directly."""
    from app.models.user import User
    from app.models.user_identity import UserIdentity
    from app.services import oauth as svc

    existing_user = User(
        id=uuid4(),
        email="carol@example.com",
        username="carol",
        password_hash=None,
        is_admin=False,
        is_verified=False,
    )
    existing_identity = UserIdentity(
        id=uuid4(),
        user_id=existing_user.id,
        provider="github",
        provider_user_id="77777",
        provider_email="carol@example.com",
    )

    call_count = 0

    async def fake_scalar(_stmt: object) -> object:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return existing_identity  # identity found on first lookup
        return existing_user  # user found on second lookup

    fake_session = AsyncMock()
    fake_session.scalar.side_effect = fake_scalar
    fake_session.add = MagicMock()

    monkeypatch.setattr(svc, "record_audit_event", AsyncMock())

    user = await svc.find_or_create_oauth_user(
        fake_session,  # type: ignore[arg-type]
        provider="github",
        provider_user_id="77777",
        email="carol@example.com",
        display_name="Carol",
        username_hint="carol",
    )

    assert user is existing_user
    # Nothing new should have been added.
    fake_session.add.assert_not_called()


# ---------------------------------------------------------------------------
# GitHub callback: error + missing config paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_github_callback_error_param_redirects_to_login(monkeypatch: pytest.MonkeyPatch) -> None:
    """If GitHub returns ?error=access_denied, redirect to /login with a message."""
    fake_session = AsyncMock()
    fake_request = _make_fake_request()
    # Patch rate limiter so it never throttles inside unit tests.
    monkeypatch.setattr(oauth_router, "_oauth_rate_limit", _passthrough_rate_limit)
    response = await oauth_router.github_oauth_callback(
        request=fake_request,
        session=fake_session,  # type: ignore[arg-type]
        code=None,
        state=None,
        error="access_denied",
    )
    assert response.status_code == 302
    assert "/login" in response.headers["location"]
    assert "error" in response.headers["location"]


@pytest.mark.asyncio
async def test_github_callback_invalid_state_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    """An invalid state token should redirect to login with an error."""
    fake_session = AsyncMock()
    fake_request = _make_fake_request()
    monkeypatch.setattr(oauth_router, "_oauth_rate_limit", _passthrough_rate_limit)
    response = await oauth_router.github_oauth_callback(
        request=fake_request,
        session=fake_session,  # type: ignore[arg-type]
        code="some-code",
        state="not-a-real-state-jwt",
        error=None,
    )
    assert response.status_code == 302
    assert "/login" in response.headers["location"]


@pytest.mark.asyncio
async def test_google_callback_error_param_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    """If Google returns ?error=access_denied, redirect to /login."""
    fake_session = AsyncMock()
    fake_request = _make_fake_request()
    monkeypatch.setattr(oauth_router, "_oauth_rate_limit", _passthrough_rate_limit)
    response = await oauth_router.google_oauth_callback(
        request=fake_request,
        session=fake_session,  # type: ignore[arg-type]
        code=None,
        state=None,
        error="access_denied",
    )
    assert response.status_code == 302
    assert "/login" in response.headers["location"]
