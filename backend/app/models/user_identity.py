from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserIdentity(Base):
    """Maps a third-party OAuth identity to an EvalLedger user account.

    A single user can have multiple identities (one per provider).  The pair
    (provider, provider_user_id) is unique, which prevents duplicate accounts
    when the same GitHub/Google user logs in more than once.
    """

    __tablename__ = "user_identities"
    __table_args__ = (UniqueConstraint("provider", "provider_user_id", name="uq_user_identity_provider"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # "github" | "google"
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    # The provider's own stable identifier for this account (integer or string)
    provider_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    # The email address the provider reported at the time of last login (may change)
    provider_email: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="identities", foreign_keys=[user_id])
