"""move raw text to the archive

Drops pdf_urls.raw_text, log_entries.raw_text and log_entries.raw_reason_action,
whose originals now live in the MongoDB raw archive, and log_entries.scraped_at,
which duplicates created_at.

Plain schema change. Nothing is live, so no text is copied first: a database that
holds rows is reset and scraped again. The downgrade brings the columns back empty.

Revision ID: 7c4d2b19a8e3
Revises: 3f1a9c7e2b54
Create Date: 2026-11-06 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c4d2b19a8e3"
down_revision: str | Sequence[str] | None = "3f1a9c7e2b54"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("pdf_urls", "raw_text")
    op.drop_column("log_entries", "raw_text")
    op.drop_column("log_entries", "raw_reason_action")
    op.drop_column("log_entries", "scraped_at")


def downgrade() -> None:
    op.add_column("log_entries", sa.Column("scraped_at", sa.DateTime(), nullable=True))
    op.add_column(
        "log_entries", sa.Column("raw_reason_action", sa.Text(), nullable=True)
    )
    op.add_column("log_entries", sa.Column("raw_text", sa.Text(), nullable=True))
    op.add_column("pdf_urls", sa.Column("raw_text", sa.Text(), nullable=True))
