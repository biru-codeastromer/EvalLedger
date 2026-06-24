"""Enforce unique API key hashes and widen corpus token counts.

- Adds a UNIQUE index on api_keys(key_hash) so a hashed secret can only
  ever map to a single key record.
- Widens reference_corpora.size_tokens to BigInteger to accommodate
  large corpora whose token counts exceed the 32-bit integer range.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260406_0006"
down_revision = "20260405_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("uq_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)
    op.alter_column(
        "reference_corpora",
        "size_tokens",
        type_=sa.BigInteger(),
        existing_type=sa.Integer(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "reference_corpora",
        "size_tokens",
        type_=sa.Integer(),
        existing_type=sa.BigInteger(),
        existing_nullable=True,
    )
    op.drop_index("uq_api_keys_key_hash", table_name="api_keys")
