"""Create the infrastructure schema_meta table.

Revision ID: 0001
Revises:
Create Date: 2026-11-09

This is not a domain model. Domain tables are a later package.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schema_meta",
        sa.Column("version", sa.String(length=64), primary_key=True),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    schema_meta = sa.table("schema_meta", sa.column("version", sa.String))
    op.bulk_insert(schema_meta, [{"version": "1"}])


def downgrade() -> None:
    op.drop_table("schema_meta")
