"""move raw text to the archive

Drops pdf_urls.raw_text, log_entries.raw_text and log_entries.raw_reason_action,
whose originals now live in the MongoDB raw archive, and log_entries.scraped_at,
which duplicates created_at.

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

# (table, key column, archive source) for each column of text that moves.
_MOVED_TEXT = (
    ("pdf_urls", "canonical_url", "police_log_text"),
    ("log_entries", "case_number", "police_log_entry_text"),
)


def upgrade() -> None:
    _require_raw_text_archived()
    op.drop_column("pdf_urls", "raw_text")
    op.drop_column("log_entries", "raw_text")
    op.drop_column("log_entries", "raw_reason_action")
    op.drop_column("log_entries", "scraped_at")


def _require_raw_text_archived() -> None:
    """Stop before dropping any text that is not in the raw archive."""
    bind = op.get_bind()
    pending = {
        source: set(
            bind.scalars(
                sa.text(f"SELECT {key} FROM {table} WHERE raw_text IS NOT NULL")
            )
        )
        for table, key, source in _MOVED_TEXT
    }
    if not any(pending.values()):
        # A new or emptied database: nothing to lose, and no need for MongoDB.
        return

    # Imported here, so databases with nothing to move never need the mongo package.
    from mongo.archive import archive_collection
    from mongo.client import MongoDB
    from mongo.raw_text import archived_keys

    collection = archive_collection(MongoDB())
    missing = {
        source: keys - archived_keys(collection, source)
        for source, keys in pending.items()
    }
    if any(missing.values()):
        counts = ", ".join(
            f"{len(keys)} of {len(pending[source])} for {source}"
            for source, keys in missing.items()
            if keys
        )
        raise RuntimeError(
            f"Raw text is not in the archive yet ({counts}). Run "
            "`python -m maintenance.archive_raw_text` from scrapers/, then migrate again."
        )


def downgrade() -> None:
    # The values stay in the archive; the columns come back empty.
    op.add_column("log_entries", sa.Column("scraped_at", sa.DateTime(), nullable=True))
    op.add_column(
        "log_entries", sa.Column("raw_reason_action", sa.Text(), nullable=True)
    )
    op.add_column("log_entries", sa.Column("raw_text", sa.Text(), nullable=True))
    op.add_column("pdf_urls", sa.Column("raw_text", sa.Text(), nullable=True))
