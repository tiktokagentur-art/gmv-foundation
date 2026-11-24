"""Add the workload credential table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-10

Upgrade only creates ``credentials``. ``schema_meta`` and every older table
stay as they are, so the previous application still runs against this schema.
Downgrade drops the new table and nothing else. The plaintext key is not a
column. ``key_hash`` is the SHA-256 hex digest.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("identity_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="credentials_pkey"),
        sa.UniqueConstraint("key_hash", name="credentials_key_hash_key"),
        sa.CheckConstraint(
            "kind IN ('service', 'worker')",
            name="credentials_kind_check",
        ),
        sa.CheckConstraint("prefix = 'gmv_wk_'", name="credentials_prefix_check"),
        sa.CheckConstraint(
            "key_hash ~ '^[0-9a-f]{64}$'",
            name="credentials_key_hash_hex_check",
        ),
    )
    op.create_index("credentials_identity_id_idx", "credentials", ["identity_id"])
    op.execute(
        "COMMENT ON TABLE credentials IS "
        "'Workload API key. key_hash is SHA-256 hex. Plaintext is not stored.'"
    )


def downgrade() -> None:
    op.drop_index("credentials_identity_id_idx", table_name="credentials")
    op.drop_table("credentials")
