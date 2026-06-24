from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.api_key import APIKey
    from app.models.audit import AuditEvent
    from app.models.benchmark import Benchmark
    from app.models.user_identity import UserIdentity
    from app.models.version import BenchmarkVersion


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # Nullable: OAuth-only users never set a password.
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(Text)
    affiliation: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Set when the account is erased (GDPR). PII is anonymized in place and the
    # row is retained so audit/benchmark foreign keys stay intact; auth rejects
    # any request for a user whose deleted_at is set.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Two FK paths from Benchmark to User (submitter_id and reviewed_by_id)
    # require foreign_keys= to be explicit on both sides of the relationship.
    benchmarks: Mapped[list[Benchmark]] = relationship(
        back_populates="submitter", foreign_keys="[Benchmark.submitter_id]"
    )
    versions: Mapped[list[BenchmarkVersion]] = relationship(back_populates="submitter")
    api_keys: Mapped[list[APIKey]] = relationship(back_populates="user")
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="actor")
    identities: Mapped[list[UserIdentity]] = relationship(back_populates="user")
