from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from app import main as main_module
from app.database import get_session
from app.main import app


class DummySession:
    pass


async def override_session() -> AsyncIterator[DummySession]:
    yield DummySession()


def test_health_reports_component_status(monkeypatch) -> None:
    async def database_ready() -> bool:
        return True

    async def redis_ready() -> bool:
        return False

    async def storage_ready() -> bool:
        return True

    monkeypatch.setattr(main_module, "_database_ready", database_ready)
    monkeypatch.setattr(main_module, "_redis_ready", redis_ready)
    monkeypatch.setattr(main_module, "_storage_ready", storage_ready)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["checks"] == {"database": True, "redis": False, "storage": True}


def test_benchmark_creation_requires_authentication() -> None:
    app.dependency_overrides[get_session] = override_session
    payload = {
        "name": "EvalLedger Sample",
        "slug": "evalledger-sample",
        "description": "A benchmark record that should only be created by authenticated users.",
        "domain": ["reasoning"],
        "task_type": "multiple_choice",
    }
    try:
        with TestClient(app) as client:
            response = client.post("/benchmarks", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_version_submission_requires_authentication() -> None:
    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            response = client.post(
                "/benchmarks/mmlu/versions",
                data={"version": "1.0.0"},
                files={"artifact": ("artifact.jsonl", b'{"prompt":"hi"}\n', "application/json")},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_admin_review_queue_requires_authentication() -> None:
    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            response = client.get("/admin/review-queue")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
