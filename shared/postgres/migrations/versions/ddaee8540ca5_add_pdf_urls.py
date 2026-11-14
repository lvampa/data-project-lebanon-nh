"""add pdf_urls

Revision ID: ddaee8540ca5
Revises: 22fc0163d5ff
Create Date: 2026-10-31 11:52:37.744550

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ddaee8540ca5"
down_revision: str | Sequence[str] | None = "22fc0163d5ff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pdf_urls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("archive_url", sa.Text(), nullable=True),
        sa.Column("log_date", sa.Date(), nullable=True),
        sa.Column("state", sa.Text(), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("entry_count", sa.Integer(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "state IN ('pending', 'in_progress', 'complete', 'error')",
            name="ck_pdf_urls_state",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_url"),
    )
    op.create_index(
        "idx_pdf_urls_state_created_at", "pdf_urls", ["state", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_pdf_urls_state_created_at", table_name="pdf_urls")
    op.drop_table("pdf_urls")
