"""End-to-end integration tests against a real Postgres + Redis.

Run with DATABASE_URL (and REDIS_URL) pointing at live services; skipped
otherwise (see conftest.py). These drive the actual ASGI app through HTTP,
exercising routing, middleware (metrics/ETag/rate-limit/idempotency), the DB,
and the auth/GDPR/report flows that the mocked unit tests cannot cover.
"""

from __future__ import annotations

import io
import os
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

from app.database import SessionLocal, engine
from app.main import app
from app.models.user import User
from app.ratelimit import set_limiter
from app.security import create_access_token

pytestmark = pytest.mark.integration


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    # ASGITransport does not run the app lifespan, so attach Redis to the rate
    # limiter manually (mirrors what lifespan does) to exercise the headers path.
    redis: Redis | None = Redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"), decode_responses=False
    )
    try:
        await redis.ping()
        set_limiter(redis)
    except Exception:
        redis = None
        set_limiter(None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    set_limiter(None)
    if redis is not None:
        await redis.aclose()
    # Dispose the pool so the next test's event loop never reuses a connection
    # bound to this (now-closing) loop.
    await engine.dispose()


async def _make_user(*, is_admin: bool = False) -> tuple[str, str]:
    async with SessionLocal() as session:
        user = User(
            email=f"it-{uuid4().hex[:10]}@example.com",
            username=f"it_{uuid4().hex[:10]}",
            is_admin=is_admin,
            is_verified=True,
        )
        session.add(user)
        await session.commit()
        return str(user.id), create_access_token(str(user.id))


async def test_health_and_metrics(client: AsyncClient) -> None:
    assert (await client.get("/health/live")).status_code == 200
    metrics = await client.get("/metrics")
    assert metrics.status_code == 200
    assert "evalledger_http_requests_total" in metrics.text


async def test_public_read_headers(client: AsyncClient) -> None:
    overview = await client.get("/stats/overview")
    assert overview.status_code == 200
    assert overview.headers.get("ETag", "").startswith('W/"')  # anonymous public GET is cacheable
    search = await client.get("/search?q=")
    assert search.status_code == 200
    assert "X-RateLimit-Limit" in search.headers  # rate-limited route exposes headers


async def test_benchmark_and_version_lifecycle(client: AsyncClient) -> None:
    _, token = await _make_user()
    headers = {"Authorization": f"Bearer {token}"}
    slug = f"it-bm-{uuid4().hex[:8]}"

    created = await client.post(
        "/benchmarks",
        headers=headers,
        json={
            "name": "IT Benchmark",
            "slug": slug,
            "description": "Integration-test benchmark exercising the full registry stack.",
            "domain": ["reasoning"],
            "task_type": "multiple_choice",
        },
    )
    assert created.status_code == 201, created.text

    files = {"artifact": ("data.jsonl", io.BytesIO(b'{"question":"hi","answer":"there"}\n'), "application/x-ndjson")}
    version = await client.post(f"/benchmarks/{slug}/versions", headers=headers, data={"version": "1.0.0"}, files=files)
    assert version.status_code == 201, version.text

    detail = await client.get(f"/benchmarks/{slug}")
    assert detail.status_code == 200
    assert detail.json()["slug"] == slug
    assert (await client.get("/search?q=")).status_code == 200


async def test_idempotency_replay(client: AsyncClient) -> None:
    _, token = await _make_user()
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": uuid4().hex}
    slug = f"it-idem-{uuid4().hex[:8]}"
    body = {
        "name": "Idem",
        "slug": slug,
        "description": "Idempotency integration-test benchmark for replay verification.",
        "domain": ["reasoning"],
        "task_type": "multiple_choice",
    }
    first = await client.post("/benchmarks", headers=headers, json=body)
    second = await client.post("/benchmarks", headers=headers, json=body)
    assert first.status_code == 201
    assert second.headers.get("Idempotency-Replay") == "true"
    assert second.status_code == first.status_code


async def test_gdpr_export_and_delete(client: AsyncClient) -> None:
    user_id, token = await _make_user()
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/auth/me", headers=headers)).status_code == 200
    export = await client.get("/auth/me/export", headers=headers)
    assert export.status_code == 200
    assert export.json()["profile"]["id"] == user_id
    assert (await client.delete("/auth/me", headers=headers)).status_code == 204
    # The token must be rejected now that the account is erased.
    assert (await client.get("/auth/me", headers=headers)).status_code == 401


async def test_report_moderation_flow(client: AsyncClient) -> None:
    _, reporter_token = await _make_user()
    _, admin_token = await _make_user(is_admin=True)
    created = await client.post(
        "/reports",
        headers={"Authorization": f"Bearer {reporter_token}"},
        json={"resource_type": "benchmark", "resource_slug": "mmlu", "reason": "mislabeled", "detail": "wrong"},
    )
    assert created.status_code == 201, created.text
    report_id = created.json()["id"]

    queue = await client.get("/reports?status=open", headers={"Authorization": f"Bearer {admin_token}"})
    assert queue.status_code == 200
    assert any(item["id"] == report_id for item in queue.json())

    resolved = await client.patch(
        f"/reports/{report_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "actioned", "resolution_note": "removed"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "actioned"


async def test_non_admin_cannot_access_moderation_queue(client: AsyncClient) -> None:
    _, token = await _make_user()
    resp = await client.get("/reports?status=open", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
