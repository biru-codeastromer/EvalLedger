"""Enforce one contamination report per (version, corpus) for idempotent re-runs."""

from __future__ import annotations

from alembic import op

revision = "20260407_0007"
down_revision = "20260406_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Collapse any pre-existing duplicate (version_id, corpus_id) rows, keeping the
    # most recent, so the unique constraint can be created on populated databases.
    op.execute(
        """
        DELETE FROM contamination_reports a
        USING contamination_reports b
        WHERE a.version_id IS NOT NULL
          AND a.version_id = b.version_id
          AND a.corpus_id = b.corpus_id
          AND a.created_at < b.created_at
        """
    )
    op.create_unique_constraint(
        "uq_contamination_version_corpus",
        "contamination_reports",
        ["version_id", "corpus_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_contamination_version_corpus",
        "contamination_reports",
        type_="unique",
    )
