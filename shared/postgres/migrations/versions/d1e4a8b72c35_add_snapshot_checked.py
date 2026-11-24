"""add address_normalizations.snapshot_checked

What a row was last looked up with (snapshot, prompt, kind, street, address), so the
geocode retries do not ask about the same row again until one of them changes.

Revision ID: d1e4a8b72c35
Revises: c9d3f6a18e52
Create Date: 2026-11-23 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1e4a8b72c35"
down_revision: str | Sequence[str] | None = "c9d3f6a18e52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "address_normalizations",
        sa.Column("snapshot_checked", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("address_normalizations", "snapshot_checked")
