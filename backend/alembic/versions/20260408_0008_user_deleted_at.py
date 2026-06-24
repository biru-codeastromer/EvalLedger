"""Add users.deleted_at for GDPR account erasure (soft-delete / anonymize)."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260408_0008"
down_revision = "20260407_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "deleted_at")
