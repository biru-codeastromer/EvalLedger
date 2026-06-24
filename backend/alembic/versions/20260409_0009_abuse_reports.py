"""Add abuse_reports table for the trust-and-safety moderation queue."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260409_0009"
down_revision = "20260408_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "abuse_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("reporter_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_slug", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolver_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("resolution_note", sa.Text()),
    )
    op.create_index("ix_abuse_reports_status_created_at", "abuse_reports", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_abuse_reports_status_created_at", table_name="abuse_reports")
    op.drop_table("abuse_reports")
