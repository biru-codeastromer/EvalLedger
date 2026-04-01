from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.benchmark import Benchmark
    from app.models.user import User
    from app.models.version import BenchmarkVersion


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    benchmark_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("benchmarks.id"))
    version_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("benchmark_versions.id"))
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(Text)
    resource_slug: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    actor: Mapped[User | None] = relationship(back_populates="audit_events")
    benchmark: Mapped[Benchmark | None] = relationship(back_populates="audit_events")
    version: Mapped[BenchmarkVersion | None] = relationship(back_populates="audit_events")
