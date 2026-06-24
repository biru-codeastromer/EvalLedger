from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class AbuseReport(Base):
    """A trust-and-safety report against a public benchmark or version.

    Loosely coupled to the reported resource by (resource_type, resource_slug)
    free-text rather than a hard FK, so a report survives the resource being
    removed and can reference resources by their public identifier.
    """

    __tablename__ = "abuse_reports"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    reporter_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_slug: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open", server_default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolver_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    resolution_note: Mapped[str | None] = mapped_column(Text)

    reporter: Mapped[User] = relationship(foreign_keys=[reporter_user_id])
    resolver: Mapped[User | None] = relationship(foreign_keys=[resolver_user_id])
