"""Tests for the admin review and verification workflow.

Covers:
- Access control: unauthenticated → 401; authenticated non-admin → 403
- review_queue: default (pending) filter, verified filter, all filter
- set_benchmark_verification: marks verified, persists note+reviewed_by, creates audit event
- set_benchmark_verification: unverification removes is_verified
- add_review_note: stores note and audit event without changing is_verified
- admin_stats: returns correct counts from DB
- recent_audit_events: action/resource_type filters applied
- benchmark_review_context: returns versions and audit trail
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.dependencies import get_current_user
from app.errors import AppError
from app.main import app
from app.models.audit import AuditEvent
from app.models.benchmark import Benchmark
from app.models.user import User
from app.routers import admin as admin_router
from app.schemas.admin import BenchmarkVerificationRequest, ReviewNoteRequest

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_admin_user() -> User:
    return User(
        id=uuid4(),
        email="admin@example.com",
        username="admin",
        password_hash=None,
        is_verified=True,
        is_admin=True,
    )


def _make_regular_user() -> User:
    return User(
        id=uuid4(),
        email="user@example.com",
        username="regularuser",
        password_hash=None,
        is_verified=False,
        is_admin=False,
    )


_NOW = datetime.now(UTC)


def _make_benchmark(*, is_verified: bool = False, slug: str = "test-bench") -> Benchmark:
    b = Benchmark(
        id=uuid4(),
        slug=slug,
        name="Test Benchmark",
        description="A test benchmark for the review workflow.",
        domain=["reasoning"],
        task_type="multiple_choice",
        total_versions=0,
        total_citations=0,
        is_verified=is_verified,
        versions=[],
    )
    # Required datetime fields (not set by the ORM without a real DB flush).
    b.created_at = _NOW
    b.updated_at = _NOW
    b.review_note = None
    b.reviewed_at = None
    b.reviewed_by_id = None
    b.reviewed_by = None
    b.submitter = None
    return b


class ScalarList:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class ExecuteRow:
    def __init__(self, benchmark, **fields):
        self._benchmark = benchmark
        self.latest_version = None
        self.latest_contamination_status = None
        self.latest_num_examples = None
        self.latest_artifact_sha256 = None
        self.latest_artifact_size_bytes = None
        for key, value in fields.items():
            setattr(self, key, value)

    def __getitem__(self, index: int):
        if index == 0:
            return self._benchmark
        raise IndexError(index)


class FakeSession:
    """Minimal async session stub for unit-testing router functions."""

    def __init__(self, scalar_values=None, scalars_values=None, execute_values=None):
        # scalar_values is an iterable that scalar() pops from in order.
        self._scalar_iter = iter(scalar_values if scalar_values is not None else [])
        self._scalars_value = scalars_values or []
        self._execute_values = execute_values
        self.added: list = []

    async def scalar(self, _stmt):
        return next(self._scalar_iter, None)

    async def scalars(self, _stmt):
        return ScalarList(self._scalars_value)

    async def execute(self, _stmt):
        if self._execute_values is not None:
            return ScalarList(self._execute_values)
        return ScalarList([ExecuteRow(item) for item in self._scalars_value])

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def refresh(self, item):
        if getattr(item, "id", None) is None:
            item.id = uuid4()
        if getattr(item, "created_at", None) is None:
            item.created_at = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Access-control tests (TestClient)
# ---------------------------------------------------------------------------


class DummySession:
    pass


async def _override_session() -> AsyncIterator[DummySession]:
    yield DummySession()


def test_review_queue_unauthenticated_returns_401() -> None:
    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            response = client.get("/admin/review-queue")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_review_queue_rejects_non_admin() -> None:
    regular_user = _make_regular_user()
    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_current_user] = lambda: regular_user
    try:
        with TestClient(app) as client:
            response = client.get("/admin/review-queue")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_admin_stats_unauthenticated_returns_401() -> None:
    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            response = client.get("/admin/stats")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_verification_endpoint_unauthenticated_returns_401() -> None:
    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            response = client.patch(
                "/admin/benchmarks/any-slug/verification",
                json={"verified": True},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


def test_review_note_endpoint_unauthenticated_returns_401() -> None:
    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            response = client.post(
                "/admin/benchmarks/any-slug/notes",
                json={"note": "needs follow-up"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# review_queue business logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_queue_default_returns_unverified() -> None:
    """Default status=pending → only unverified benchmarks returned."""
    unverified = _make_benchmark(is_verified=False)
    session = FakeSession(scalars_values=[unverified])
    result = await admin_router.review_queue(session=session, _=_make_admin_user())
    assert len(result) == 1
    assert result[0].slug == "test-bench"
    assert result[0].is_verified is False


@pytest.mark.asyncio
async def test_review_queue_verified_filter() -> None:
    """status=verified → filter is honoured (DB returns verified benchmark)."""
    verified = _make_benchmark(is_verified=True, slug="verified-bench")
    session = FakeSession(scalars_values=[verified])
    result = await admin_router.review_queue(session=session, _=_make_admin_user(), status="verified")
    assert len(result) == 1
    assert result[0].is_verified is True


@pytest.mark.asyncio
async def test_review_queue_all_filter_returns_everything() -> None:
    """status=all → both verified and unverified come back."""
    b1 = _make_benchmark(is_verified=False, slug="unverified")
    b2 = _make_benchmark(is_verified=True, slug="verified")
    session = FakeSession(scalars_values=[b1, b2])
    result = await admin_router.review_queue(session=session, _=_make_admin_user(), status="all")
    assert len(result) == 2


@pytest.mark.asyncio
async def test_review_queue_returns_review_fields() -> None:
    """ReviewQueueItem exposes review_note, reviewed_at, reviewed_by."""
    b = _make_benchmark()
    b.review_note = "Check the license."
    b.reviewed_at = datetime.now(UTC)
    session = FakeSession(scalars_values=[b])
    result = await admin_router.review_queue(session=session, _=_make_admin_user())
    assert result[0].review_note == "Check the license."
    assert result[0].reviewed_at is not None


# ---------------------------------------------------------------------------
# set_benchmark_verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_verification_marks_benchmark_verified(monkeypatch) -> None:
    benchmark = _make_benchmark(is_verified=False)
    admin = _make_admin_user()
    session = FakeSession(scalar_values=[benchmark])

    async def _fake_record(*_args, **_kwargs):
        return AuditEvent(id=uuid4(), action="benchmark.verified", resource_type="benchmark")

    monkeypatch.setattr(admin_router, "record_audit_event", _fake_record)

    payload = BenchmarkVerificationRequest(verified=True, note="Looks good.")
    result = await admin_router.set_benchmark_verification(
        slug="test-bench", payload=payload, session=session, current_user=admin
    )
    assert result.benchmark.is_verified is True


@pytest.mark.asyncio
async def test_set_verification_persists_review_note(monkeypatch) -> None:
    """Verification note is written to benchmark.review_note and reviewed_by_id."""
    benchmark = _make_benchmark(is_verified=False)
    admin = _make_admin_user()
    session = FakeSession(scalar_values=[benchmark])

    async def _fake_record(*_args, **_kwargs):
        return AuditEvent(id=uuid4(), action="benchmark.verified", resource_type="benchmark")

    monkeypatch.setattr(admin_router, "record_audit_event", _fake_record)

    payload = BenchmarkVerificationRequest(verified=True, note="Approved after review.")
    await admin_router.set_benchmark_verification(
        slug="test-bench", payload=payload, session=session, current_user=admin
    )
    assert benchmark.review_note == "Approved after review."
    assert benchmark.reviewed_by_id == admin.id
    assert benchmark.reviewed_at is not None


@pytest.mark.asyncio
async def test_set_verification_creates_audit_event(monkeypatch) -> None:
    """record_audit_event is called with the correct action."""
    benchmark = _make_benchmark(is_verified=False)
    admin = _make_admin_user()
    session = FakeSession(scalar_values=[benchmark])
    recorded_kwargs: dict = {}

    async def _capture_record(_session, **kwargs):
        recorded_kwargs.update(kwargs)
        return AuditEvent(id=uuid4(), action=kwargs["action"], resource_type="benchmark")

    monkeypatch.setattr(admin_router, "record_audit_event", _capture_record)

    payload = BenchmarkVerificationRequest(verified=True)
    await admin_router.set_benchmark_verification(
        slug="test-bench", payload=payload, session=session, current_user=admin
    )
    assert recorded_kwargs["action"] == "benchmark.verified"
    assert recorded_kwargs["metadata"]["verified"] is True


@pytest.mark.asyncio
async def test_unverification_removes_is_verified(monkeypatch) -> None:
    benchmark = _make_benchmark(is_verified=True)
    admin = _make_admin_user()
    session = FakeSession(scalar_values=[benchmark])

    async def _fake_record(*_args, **_kwargs):
        return AuditEvent(id=uuid4(), action="benchmark.unverified", resource_type="benchmark")

    monkeypatch.setattr(admin_router, "record_audit_event", _fake_record)

    payload = BenchmarkVerificationRequest(verified=False, note="License issue found.")
    result = await admin_router.set_benchmark_verification(
        slug="test-bench", payload=payload, session=session, current_user=admin
    )
    assert result.benchmark.is_verified is False
    assert benchmark.review_note == "License issue found."


@pytest.mark.asyncio
async def test_verification_raises_404_for_missing_benchmark(monkeypatch) -> None:
    session = FakeSession(scalar_values=[None])
    payload = BenchmarkVerificationRequest(verified=True)
    with pytest.raises(AppError) as exc_info:
        await admin_router.set_benchmark_verification(
            slug="nonexistent", payload=payload, session=session, current_user=_make_admin_user()
        )
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# add_review_note
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_review_note_stores_note_without_changing_verification(monkeypatch) -> None:
    benchmark = _make_benchmark(is_verified=False)
    admin = _make_admin_user()
    session = FakeSession(scalar_values=[benchmark])

    async def _fake_record(*_args, **_kwargs):
        return AuditEvent(id=uuid4(), action="benchmark.review_note", resource_type="benchmark")

    monkeypatch.setattr(admin_router, "record_audit_event", _fake_record)

    payload = ReviewNoteRequest(note="Waiting for submitter to clarify license.")
    result = await admin_router.add_review_note(
        slug="test-bench", payload=payload, session=session, current_user=admin
    )
    # Verification status unchanged
    assert benchmark.is_verified is False
    # Note persisted
    assert benchmark.review_note == "Waiting for submitter to clarify license."
    assert benchmark.reviewed_by_id == admin.id
    assert result.benchmark.is_verified is False


@pytest.mark.asyncio
async def test_add_review_note_creates_audit_event(monkeypatch) -> None:
    benchmark = _make_benchmark()
    admin = _make_admin_user()
    session = FakeSession(scalar_values=[benchmark])
    recorded_kwargs: dict = {}

    async def _capture(*_args, **kwargs):
        recorded_kwargs.update(kwargs)
        return AuditEvent(id=uuid4(), action=kwargs["action"], resource_type="benchmark")

    monkeypatch.setattr(admin_router, "record_audit_event", _capture)

    payload = ReviewNoteRequest(note="Flagged for closer inspection.")
    await admin_router.add_review_note(
        slug="test-bench", payload=payload, session=session, current_user=admin
    )
    assert recorded_kwargs["action"] == "benchmark.review_note"
    assert recorded_kwargs["summary"] == "Flagged for closer inspection."


@pytest.mark.asyncio
async def test_add_review_note_raises_404_for_missing_benchmark(monkeypatch) -> None:
    session = FakeSession(scalar_values=[None])
    with pytest.raises(AppError) as exc_info:
        await admin_router.add_review_note(
            slug="ghost",
            payload=ReviewNoteRequest(note="Nope"),
            session=session,
            current_user=_make_admin_user(),
        )
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# admin_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_stats_returns_correct_counts() -> None:
    # scalar() is called 5 times in order: total, unverified, verified,
    # pending_contamination, flagged_contamination
    session = FakeSession(scalar_values=[100, 20, 80, 5, 3])
    result = await admin_router.admin_stats(session=session, _=_make_admin_user())
    assert result.total_benchmarks == 100
    assert result.unverified_count == 20
    assert result.verified_count == 80
    assert result.contamination_pending_count == 5
    assert result.contamination_flagged_count == 3


@pytest.mark.asyncio
async def test_admin_stats_handles_empty_database() -> None:
    """All counts return 0 when DB is empty (scalar returns None → coerced to 0)."""
    session = FakeSession(scalar_values=[None, None, None, None, None])
    result = await admin_router.admin_stats(session=session, _=_make_admin_user())
    assert result.total_benchmarks == 0
    assert result.unverified_count == 0
    assert result.contamination_flagged_count == 0


# ---------------------------------------------------------------------------
# recent_audit_events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_events_returns_list() -> None:
    event = AuditEvent(
        id=uuid4(),
        action="benchmark.verified",
        resource_type="benchmark",
        resource_slug="mmlu",
        created_at=datetime.now(UTC),
    )
    event.actor = None
    session = FakeSession(scalars_values=[event])
    result = await admin_router.recent_audit_events(session=session, _=_make_admin_user())
    assert len(result) == 1
    assert result[0].action == "benchmark.verified"


# ---------------------------------------------------------------------------
# benchmark_review_context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_context_raises_404_for_missing_benchmark() -> None:
    session = FakeSession(scalar_values=[None])
    with pytest.raises(AppError) as exc_info:
        await admin_router.benchmark_review_context(
            slug="ghost", session=session, _=_make_admin_user()
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_review_context_returns_versions_and_audit_history() -> None:
    from app.models.version import BenchmarkVersion

    benchmark = _make_benchmark()
    v = BenchmarkVersion(
        id=uuid4(),
        benchmark_id=benchmark.id,
        version="1.0.0",
        contamination_status="clean",
        created_at=datetime.now(UTC),
    )
    v.submitter = None
    benchmark.versions = [v]
    benchmark.audit_events = []
    session = FakeSession(scalar_values=[benchmark])

    result = await admin_router.benchmark_review_context(
        slug="test-bench", session=session, _=_make_admin_user()
    )
    assert len(result.versions) == 1
    assert result.versions[0].version == "1.0.0"
    assert result.versions[0].contamination_status == "clean"
    assert result.audit_history == []
