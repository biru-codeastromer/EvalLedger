"""Tests for the abuse-report / moderation endpoints (routers/reports.py)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.report import AbuseReport
from app.models.user import User
from app.routers import reports as reports_router
from app.schemas.report import ReportCreateRequest, ReportResolveRequest


class _FakeSession:
    def __init__(self, scalar_result: object | None = None) -> None:
        self._scalar_result = scalar_result
        self.added: list[object] = []

    def add(self, item: object) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = uuid4()  # type: ignore[attr-defined]
            if getattr(item, "created_at", None) is None:
                item.created_at = datetime.now(UTC)  # type: ignore[attr-defined]

    async def commit(self) -> None:
        return None

    async def refresh(self, item: object) -> None:
        if getattr(item, "id", None) is None:
            item.id = uuid4()  # type: ignore[attr-defined]
        if getattr(item, "created_at", None) is None:
            item.created_at = datetime.now(UTC)  # type: ignore[attr-defined]

    async def scalar(self, _stmt: object) -> object | None:
        return self._scalar_result


def _user(is_admin: bool = False) -> User:
    return User(id=uuid4(), email="u@x.com", username="u", is_admin=is_admin, is_verified=False)


@pytest.mark.asyncio
async def test_create_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reports_router, "record_audit_event", AsyncMock())
    session = _FakeSession()
    payload = ReportCreateRequest(
        resource_type="benchmark", resource_slug="mmlu", reason="mislabeled", detail="wrong license"
    )
    result = await reports_router.create_report(payload, session, _user())  # type: ignore[arg-type]
    assert result.status == "open"
    assert result.reason == "mislabeled"
    assert result.resource_slug == "mmlu"
    assert any(isinstance(item, AbuseReport) for item in session.added)


@pytest.mark.asyncio
async def test_resolve_report_not_found() -> None:
    from app.errors import AppError

    session = _FakeSession(scalar_result=None)
    payload = ReportResolveRequest(status="dismissed", resolution_note="n/a")
    with pytest.raises(AppError) as exc_info:
        await reports_router.resolve_report(str(uuid4()), payload, session, _user(is_admin=True))  # type: ignore[arg-type]
    assert exc_info.value.code == "report_not_found"


@pytest.mark.asyncio
async def test_resolve_report_actioned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reports_router, "record_audit_event", AsyncMock())
    report = AbuseReport(
        id=uuid4(),
        reporter_user_id=uuid4(),
        resource_type="benchmark",
        resource_slug="mmlu",
        reason="malicious",
        status="open",
        created_at=datetime.now(UTC),
    )
    admin = _user(is_admin=True)
    session = _FakeSession(scalar_result=report)
    payload = ReportResolveRequest(status="actioned", resolution_note="removed")
    result = await reports_router.resolve_report(str(report.id), payload, session, admin)  # type: ignore[arg-type]
    assert result.status == "actioned"
    assert result.resolved_at is not None
    assert result.resolver_user_id == admin.id
    assert result.resolution_note == "removed"
