"""Tests for GDPR account export and erasure (services/account.py + auth rejection)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.api_key import APIKey
from app.models.user import User
from app.models.user_identity import UserIdentity
from app.services import account as account_service


class _FakeScalars:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def all(self) -> list[object]:
        return self._items


class _FakeSession:
    """Async session stub that returns queued scalars() results in order."""

    def __init__(self, scalars_queue: list[list[object]]) -> None:
        self._queue = list(scalars_queue)
        self.deleted: list[object] = []
        self.added: list[object] = []

    async def scalars(self, _stmt: object) -> _FakeScalars:
        return _FakeScalars(self._queue.pop(0) if self._queue else [])

    async def scalar(self, _stmt: object) -> object | None:
        return None

    async def flush(self) -> None:
        return None

    def add(self, item: object) -> None:
        self.added.append(item)

    async def delete(self, item: object) -> None:
        self.deleted.append(item)


def _user() -> User:
    return User(
        id=uuid4(),
        email="researcher@example.com",
        username="researcher",
        password_hash="$2b$12$hash",
        display_name="Researcher",
        affiliation="Lab",
        is_verified=True,
        is_admin=True,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_export_user_data_shape() -> None:
    user = _user()
    session = _FakeSession([[], [], [], [], []])  # identities, keys, benchmarks, versions, audit
    payload = await account_service.export_user_data(session, user)  # type: ignore[arg-type]
    assert payload["profile"]["email"] == "researcher@example.com"
    assert payload["profile"]["username"] == "researcher"
    for key in ("oauth_identities", "api_keys", "benchmarks", "versions", "audit_events"):
        assert key in payload and payload[key] == []
    assert "exported_at" in payload


@pytest.mark.asyncio
async def test_delete_user_anonymizes_and_revokes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(account_service, "record_audit_event", AsyncMock())
    user = _user()
    original_id = user.id
    key1 = APIKey(user_id=user.id, key_hash="a", is_active=True)
    key2 = APIKey(user_id=user.id, key_hash="b", is_active=True)
    identity = UserIdentity(user_id=user.id, provider="github", provider_user_id="123", provider_email="x@y.z")
    session = _FakeSession([[key1, key2], [identity]])  # api_keys, then identities

    await account_service.delete_user(session, user)  # type: ignore[arg-type]

    assert user.email == f"deleted-{original_id}@deleted.evalledger.app"
    assert user.username.startswith("deleted_")
    assert user.display_name is None and user.affiliation is None and user.password_hash is None
    assert user.is_admin is False and user.is_verified is False
    assert user.deleted_at is not None
    assert key1.is_active is False and key2.is_active is False
    assert identity in session.deleted


@pytest.mark.asyncio
async def test_get_current_user_rejects_deleted_account() -> None:
    from app.dependencies import get_current_user
    from app.errors import AppError
    from app.security import create_access_token

    user = _user()
    user.deleted_at = datetime.now(UTC)
    session = MagicMock()
    session.scalar = AsyncMock(return_value=user)
    request = MagicMock()
    request.state.request_id = "req-1"
    request.url.path = "/auth/me"

    token = create_access_token(str(user.id))
    with pytest.raises(AppError) as exc_info:
        await get_current_user(request, session, authorization=f"Bearer {token}", x_api_key=None)
    assert exc_info.value.code == "account_deleted"
