"""Add targeted indexes for hot read paths."""

from __future__ import annotations

from alembic import op

revision = "20260405_0005"
down_revision = "20260403_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_benchmark_versions_benchmark_created_at",
        "benchmark_versions",
        ["benchmark_id", "created_at"],
    )
    op.create_index(
        "ix_benchmarks_verified_created_at",
        "benchmarks",
        ["is_verified", "created_at"],
    )
    op.create_index(
        "ix_benchmarks_submitter_updated_at",
        "benchmarks",
        ["submitter_id", "updated_at", "created_at"],
    )
    op.create_index(
        "ix_audit_events_resource_slug_created_at",
        "audit_events",
        ["resource_slug", "created_at"],
    )
    op.create_index(
        "ix_api_keys_user_created_at",
        "api_keys",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_api_keys_user_created_at", table_name="api_keys")
    op.drop_index("ix_audit_events_resource_slug_created_at", table_name="audit_events")
    op.drop_index("ix_benchmarks_submitter_updated_at", table_name="benchmarks")
    op.drop_index("ix_benchmarks_verified_created_at", table_name="benchmarks")
    op.drop_index("ix_benchmark_versions_benchmark_created_at", table_name="benchmark_versions")
