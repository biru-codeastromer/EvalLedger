"""Add OAuth provider identities and make password_hash nullable."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260403_0003"
down_revision = "20260402_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Make password_hash nullable so OAuth-only users need no password.
    op.alter_column("users", "password_hash", nullable=True)

    # 2. Create user_identities table to track third-party OAuth accounts.
    op.create_table(
        "user_identities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # "github" or "google"
        sa.Column("provider", sa.Text(), nullable=False),
        # The provider's own stable user identifier
        sa.Column("provider_user_id", sa.Text(), nullable=False),
        # Email reported by the provider (may be NULL for GitHub private-email accounts)
        sa.Column("provider_email", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_user_identity_provider"),
    )

    op.create_index("ix_user_identities_user_id", "user_identities", ["user_id"])
    op.create_index("ix_user_identities_provider_uid", "user_identities", ["provider", "provider_user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_identities_provider_uid", table_name="user_identities")
    op.drop_index("ix_user_identities_user_id", table_name="user_identities")
    op.drop_table("user_identities")
    op.alter_column("users", "password_hash", nullable=False)
