from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.benchmark import Benchmark
from app.models.user import User
from app.models.version import BenchmarkVersion


async def record_audit_event(
    session: AsyncSession,
    *,
    action: str,
    resource_type: str,
    actor: User | None = None,
    benchmark: Benchmark | None = None,
    version: BenchmarkVersion | None = None,
    resource_id: str | None = None,
    resource_slug: str | None = None,
    summary: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=actor.id if actor else None,
        benchmark_id=benchmark.id if benchmark else None,
        version_id=version.id if version else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_slug=resource_slug,
        summary=summary,
        metadata_json=metadata,
    )
    session.add(event)
    await session.flush()
    return event
