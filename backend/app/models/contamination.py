from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.version import BenchmarkVersion


class ReferenceCorpus(Base):
    __tablename__ = "reference_corpora"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str | None] = mapped_column(Text)
    size_tokens: Mapped[int | None] = mapped_column(BigInteger)
    source_url: Mapped[str | None] = mapped_column(Text)
    minhash_index_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    reports: Mapped[list[ContaminationReport]] = relationship(back_populates="corpus")


class ContaminationReport(Base):
    __tablename__ = "contamination_reports"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    version_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("benchmark_versions.id")
    )
    corpus_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("reference_corpora.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    overlap_score: Mapped[float | None] = mapped_column(Float)
    num_flagged_examples: Mapped[int | None] = mapped_column(Integer)
    flagged_examples: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    minhash_threshold: Mapped[float] = mapped_column(Float, default=0.8, server_default="0.8")
    job_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    job_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    version: Mapped[BenchmarkVersion | None] = relationship(back_populates="contamination_reports")
    corpus: Mapped[ReferenceCorpus] = relationship(back_populates="reports")

