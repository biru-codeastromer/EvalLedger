from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import UploadFile

from app.errors import AppError
from app.models.benchmark import Benchmark
from app.models.contamination import ReferenceCorpus
from app.models.user import User
from app.routers import versions as versions_router


class ScalarList:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class FakeSession:
    def __init__(self) -> None:
        self.added = []

    async def scalar(self, _statement):
        return None

    async def scalars(self, _statement):
        return ScalarList(
            [
                ReferenceCorpus(
                    id=uuid4(),
                    name="The Pile",
                    description="sample",
                    version="sample",
                    source_url="https://pile.eleuther.ai/",
                    minhash_index_path="corpora/pile.pkl",
                    is_active=True,
                )
            ]
        )

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def refresh(self, _item):
        if getattr(_item, "id", None) is None:
            _item.id = uuid4()
        if getattr(_item, "created_at", None) is None:
            _item.created_at = datetime.now(UTC)
        return None


@pytest.mark.asyncio
async def test_create_version_returns_canonical_id(monkeypatch) -> None:
    benchmark = Benchmark(
        id=uuid4(),
        name="MMLU",
        slug="mmlu",
        description="Massive multitask language understanding for model evaluation.",
        domain=["reasoning"],
        task_type="multiple_choice",
        total_versions=0,
        total_citations=0,
        versions=[],
    )

    async def fake_fetch_benchmark(_session, _slug: str):
        return benchmark

    async def fake_upload(*_args, **_kwargs):
        return SimpleNamespace(
            storage_key="benchmarks/mmlu/artifact.jsonl",
            artifact_url="benchmarks/mmlu/artifact.jsonl",
            size_bytes=32,
            sha256="abc123",
        )

    monkeypatch.setattr(versions_router, "_fetch_benchmark", fake_fetch_benchmark)
    monkeypatch.setattr(versions_router.storage_service, "upload_upload_file", fake_upload)
    monkeypatch.setattr(
        versions_router.run_contamination_check,
        "delay",
        lambda *_args, **_kwargs: SimpleNamespace(id="job-123"),
    )

    response = await versions_router.create_version(
        slug="mmlu",
        session=FakeSession(),
        artifact=UploadFile(filename="artifact.jsonl", file=BytesIO(b'{"text":"hello"}')),
        version="1.0.0",
        current_user=User(
            id=uuid4(),
            email="researcher@example.com",
            username="researcher",
            password_hash="not-used",
            is_verified=False,
            is_admin=False,
        ),
    )

    assert response.canonical_id == "el:mmlu:1.0.0"
    assert response.contamination_job_ids == ["job-123"]


@pytest.mark.asyncio
async def test_create_version_rejects_invalid_release_date(monkeypatch) -> None:
    benchmark = Benchmark(
        id=uuid4(),
        name="MMLU",
        slug="mmlu",
        description="Massive multitask language understanding for model evaluation.",
        domain=["reasoning"],
        task_type="multiple_choice",
        total_versions=0,
        total_citations=0,
        versions=[],
    )

    async def fake_fetch_benchmark(_session, _slug: str):
        return benchmark

    async def fake_upload(*_args, **_kwargs):
        return SimpleNamespace(
            storage_key="benchmarks/mmlu/artifact.jsonl",
            artifact_url="benchmarks/mmlu/artifact.jsonl",
            size_bytes=32,
            sha256="abc123",
        )

    monkeypatch.setattr(versions_router, "_fetch_benchmark", fake_fetch_benchmark)
    monkeypatch.setattr(versions_router.storage_service, "upload_upload_file", fake_upload)

    with pytest.raises(AppError) as caught_error:
        await versions_router.create_version(
            slug="mmlu",
            session=FakeSession(),
            artifact=UploadFile(filename="artifact.jsonl", file=BytesIO(b'{"text":"hello"}')),
            version="1.0.0",
            released_at="not-a-date",
            current_user=User(
                id=uuid4(),
                email="researcher@example.com",
                username="researcher",
                password_hash="not-used",
                is_verified=False,
                is_admin=False,
            ),
        )

    assert caught_error.value.code == "invalid_release_date"
