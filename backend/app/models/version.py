from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.benchmark import Benchmark
    from app.models.contamination import ContaminationReport
    from app.models.user import User


class BenchmarkVersion(Base):
    __tablename__ = "benchmark_versions"
    __table_args__ = (UniqueConstraint("benchmark_id", "version", name="uq_benchmark_version"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    benchmark_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("benchmarks.id"), nullable=False
    )
    version: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_sha256: Mapped[str | None] = mapped_column(Text)
    artifact_url: Mapped[str | None] = mapped_column(Text)
    artifact_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    num_examples: Mapped[int | None] = mapped_column(Integer)
    splits: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    language: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    license: Mapped[str | None] = mapped_column(Text)
    paper_url: Mapped[str | None] = mapped_column(Text)
    paper_arxiv_id: Mapped[str | None] = mapped_column(Text)
    github_url: Mapped[str | None] = mapped_column(Text)
    citation_string: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    release_notes: Mapped[str | None] = mapped_column(Text)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitter_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    contamination_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending", server_default="pending"
    )

    benchmark: Mapped[Benchmark] = relationship(back_populates="versions")
    submitter: Mapped[User | None] = relationship(back_populates="versions")
    contamination_reports: Mapped[list[ContaminationReport]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )
    citations: Mapped[list[Citation]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("benchmark_versions.id"), nullable=False
    )
    cited_by_url: Mapped[str | None] = mapped_column(Text)
    cited_by_title: Mapped[str | None] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    version: Mapped[BenchmarkVersion] = relationship(back_populates="citations")
