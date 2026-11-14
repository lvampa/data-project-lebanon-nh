"""add police log ingest columns

Plain schema change. Nothing is live, so no data is carried over: a database that
has rows in these tables is reset and scraped again.

Revision ID: 3f1a9c7e2b54
Revises: ddaee8540ca5
Create Date: 2026-11-06 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3f1a9c7e2b54"
down_revision: str | Sequence[str] | None = "ddaee8540ca5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _add_log_entry_columns()
    _replace_pdf_url_entry_count()
    _add_pdf_url_error_kind()


def _add_log_entry_columns() -> None:
    op.add_column("log_entries", sa.Column("log_date", sa.Date(), nullable=False))
    op.add_column("log_entries", sa.Column("place_code", sa.Text(), nullable=True))
    op.add_column("log_entries", sa.Column("officer_code", sa.Text(), nullable=True))
    op.add_column(
        "log_entries", sa.Column("refer_to", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "log_entries",
        sa.Column(
            "disposition_unmatched",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    op.add_column(
        "log_entries",
        sa.Column(
            "missing_from_parse", sa.Boolean(), server_default="false", nullable=False
        ),
    )
    op.add_column(
        "log_entries", sa.Column("parser_version", sa.Integer(), nullable=True)
    )
    op.add_column("log_entries", sa.Column("created_at", sa.DateTime(), nullable=False))
    op.add_column("log_entries", sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.alter_column("log_entries", "case_number", nullable=False)
    op.create_index("idx_log_entries_log_date", "log_entries", ["log_date"])


def _replace_pdf_url_entry_count() -> None:
    for column in ("parsed_count", "stored_count", "skipped_count", "header_lines"):
        op.add_column("pdf_urls", sa.Column(column, sa.Integer(), nullable=True))
    op.add_column("pdf_urls", sa.Column("parser_version", sa.Integer(), nullable=True))
    op.add_column("pdf_urls", sa.Column("content_hash", sa.Text(), nullable=True))
    op.add_column("pdf_urls", sa.Column("extractor_version", sa.Text(), nullable=True))
    op.drop_column("pdf_urls", "entry_count")


def _add_pdf_url_error_kind() -> None:
    op.add_column("pdf_urls", sa.Column("error_kind", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_pdf_urls_error_kind",
        "pdf_urls",
        "error_kind IN ('download', 'parse', 'save')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_pdf_urls_error_kind", "pdf_urls", type_="check")
    op.drop_column("pdf_urls", "error_kind")

    op.add_column("pdf_urls", sa.Column("entry_count", sa.Integer(), nullable=True))
    for column in (
        "extractor_version",
        "content_hash",
        "parser_version",
        "header_lines",
        "skipped_count",
        "stored_count",
        "parsed_count",
    ):
        op.drop_column("pdf_urls", column)

    op.alter_column("log_entries", "case_number", nullable=True)
    op.drop_index("idx_log_entries_log_date", table_name="log_entries")
    for column in (
        "updated_at",
        "created_at",
        "parser_version",
        "missing_from_parse",
        "disposition_unmatched",
        "refer_to",
        "officer_code",
        "place_code",
        "log_date",
    ):
        op.drop_column("log_entries", column)
