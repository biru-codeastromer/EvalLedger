"""Add review-tracking fields to benchmarks.

Adds three columns to the benchmarks table:
- review_note  : most recent reviewer note (persisted for quick UI access)
- reviewed_at  : timestamp of the last review action
- reviewed_by_id: FK to users — who made the last review decision
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260403_0004"
down_revision = "20260403_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("benchmarks", sa.Column("review_note", sa.Text(), nullable=True))
    op.add_column("benchmarks", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "benchmarks",
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_benchmarks_reviewed_by_id",
        "benchmarks",
        "users",
        ["reviewed_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_benchmarks_reviewed_by_id", "benchmarks", ["reviewed_by_id"])


def downgrade() -> None:
    op.drop_index("ix_benchmarks_reviewed_by_id", table_name="benchmarks")
    op.drop_constraint("fk_benchmarks_reviewed_by_id", "benchmarks", type_="foreignkey")
    op.drop_column("benchmarks", "reviewed_by_id")
    op.drop_column("benchmarks", "reviewed_at")
    op.drop_column("benchmarks", "review_note")
