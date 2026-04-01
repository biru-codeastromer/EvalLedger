"""Initial EvalLedger schema."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260401_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("username", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text()),
        sa.Column("bio", sa.Text()),
        sa.Column("website", sa.Text()),
        sa.Column("affiliation", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("name", sa.Text()),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "benchmarks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("domain", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("task_type", sa.Text()),
        sa.Column("submitter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("total_versions", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_citations", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("search_vector", postgresql.TSVECTOR()),
    )

    op.create_table(
        "reference_corpora",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("version", sa.Text()),
        sa.Column("size_tokens", sa.BigInteger()),
        sa.Column("source_url", sa.Text()),
        sa.Column("minhash_index_path", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "benchmark_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("benchmark_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("benchmarks.id"), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("artifact_sha256", sa.Text()),
        sa.Column("artifact_url", sa.Text()),
        sa.Column("artifact_size_bytes", sa.BigInteger()),
        sa.Column("num_examples", sa.Integer()),
        sa.Column("splits", postgresql.JSONB()),
        sa.Column("language", postgresql.ARRAY(sa.Text())),
        sa.Column("license", sa.Text()),
        sa.Column("paper_url", sa.Text()),
        sa.Column("paper_arxiv_id", sa.Text()),
        sa.Column("github_url", sa.Text()),
        sa.Column("citation_string", sa.Text()),
        sa.Column("metadata", postgresql.JSONB()),
        sa.Column("release_notes", sa.Text()),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("submitter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("contamination_status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.UniqueConstraint("benchmark_id", "version", name="uq_benchmark_version"),
    )

    op.create_table(
        "contamination_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("benchmark_versions.id")),
        sa.Column("corpus_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reference_corpora.id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("overlap_score", sa.Float()),
        sa.Column("num_flagged_examples", sa.Integer()),
        sa.Column("flagged_examples", postgresql.JSONB()),
        sa.Column("minhash_threshold", sa.Float(), nullable=False, server_default=sa.text("0.8")),
        sa.Column("job_started_at", sa.DateTime(timezone=True)),
        sa.Column("job_completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("benchmark_versions.id"), nullable=False),
        sa.Column("cited_by_url", sa.Text()),
        sa.Column("cited_by_title", sa.Text()),
        sa.Column("context", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_index("ix_benchmarks_search_vector", "benchmarks", ["search_vector"], postgresql_using="gin")
    op.create_index("ix_benchmark_versions_status", "benchmark_versions", ["contamination_status"])
    op.create_index("ix_contamination_reports_version_id", "contamination_reports", ["version_id"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_benchmark_search_vector()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.search_vector :=
            setweight(to_tsvector('english', coalesce(NEW.name, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(NEW.slug, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(array_to_string(NEW.domain, ' '), '')), 'C') ||
            setweight(to_tsvector('english', coalesce(NEW.task_type, '')), 'C');
          NEW.updated_at := now();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_benchmarks_search_vector
        BEFORE INSERT OR UPDATE ON benchmarks
        FOR EACH ROW
        EXECUTE FUNCTION set_benchmark_search_vector();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_benchmarks_search_vector ON benchmarks")
    op.execute("DROP FUNCTION IF EXISTS set_benchmark_search_vector")
    op.drop_index("ix_contamination_reports_version_id", table_name="contamination_reports")
    op.drop_index("ix_benchmark_versions_status", table_name="benchmark_versions")
    op.drop_index("ix_benchmarks_search_vector", table_name="benchmarks")
    op.drop_table("citations")
    op.drop_table("contamination_reports")
    op.drop_table("benchmark_versions")
    op.drop_table("reference_corpora")
    op.drop_table("benchmarks")
    op.drop_table("api_keys")
    op.drop_table("users")

