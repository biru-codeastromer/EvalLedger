"""Add admin roles, audit events, and operational indexes."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260402_0002"
down_revision = "20260401_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("benchmark_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("benchmarks.id")),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("benchmark_versions.id")),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text()),
        sa.Column("resource_slug", sa.Text()),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("metadata", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_index("ix_benchmarks_submitter_id", "benchmarks", ["submitter_id"])
    op.create_index("ix_benchmark_versions_submitter_id", "benchmark_versions", ["submitter_id"])
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_benchmark_id", "audit_events", ["benchmark_id"])
    op.create_index("ix_audit_events_version_id", "audit_events", ["version_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_version_id", table_name="audit_events")
    op.drop_index("ix_audit_events_benchmark_id", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_index("ix_benchmark_versions_submitter_id", table_name="benchmark_versions")
    op.drop_index("ix_benchmarks_submitter_id", table_name="benchmarks")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_table("audit_events")
    op.drop_column("users", "is_admin")
