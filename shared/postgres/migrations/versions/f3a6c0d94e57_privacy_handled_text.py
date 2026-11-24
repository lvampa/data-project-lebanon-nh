"""remember the text a person handled, so a changed text is held again

`privacy_handled_text` is the lowercase normalized text of a location when `privacy-holds
handled` released it. If `normalize` later rewrites the text, `privacy-holds mark` holds the
location again.

A database that already has the column, from an earlier version of the previous migration,
keeps it, so this adds it only when it is missing.

Revision ID: f3a6c0d94e57
Revises: e2f5b9c83d46
Create Date: 2026-11-24 15:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f3a6c0d94e57"
down_revision: str | Sequence[str] | None = "e2f5b9c83d46"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE address_normalizations "
        "ADD COLUMN IF NOT EXISTS privacy_handled_text text"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE address_normalizations DROP COLUMN IF EXISTS privacy_handled_text"
    )
