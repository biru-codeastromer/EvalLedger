from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.audit import AuditEvent
    from app.models.user import User
    from app.models.version import BenchmarkVersion


class Benchmark(Base):
    __tablename__ = "benchmarks"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    task_type: Mapped[str | None] = mapped_column(Text)
    submitter_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    total_versions: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_citations: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    # Review tracking — updated on each verification decision or standalone note.
    # Persisted on the benchmark for quick UI access without scanning audit logs.
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    # Two FK paths to users require explicit foreign_keys= on each relationship.
    submitter: Mapped[User | None] = relationship(
        back_populates="benchmarks", foreign_keys=[submitter_id]
    )
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_id])
    versions: Mapped[list[BenchmarkVersion]] = relationship(
        back_populates="benchmark", cascade="all, delete-orphan", order_by="BenchmarkVersion.created_at.desc()"
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="benchmark")
