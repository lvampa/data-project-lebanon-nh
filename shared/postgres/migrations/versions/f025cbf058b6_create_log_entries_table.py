"""create log_entries table

Revision ID: f025cbf058b6
Revises:
Create Date: 2026-05-25 12:23:26.173135

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f025cbf058b6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "log_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("case_number", sa.Text(), nullable=True, unique=True),
        sa.Column("reported_at", sa.DateTime(), nullable=True),
        sa.Column("incident_type", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("officer", sa.Text(), nullable=True),
        sa.Column("disposition", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("parse_error", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_log_entries_reported_at", "log_entries", ["reported_at"])
    op.create_index("idx_log_entries_incident_type", "log_entries", ["incident_type"])


def downgrade() -> None:
    op.drop_index("idx_log_entries_incident_type", table_name="log_entries")
    op.drop_index("idx_log_entries_reported_at", table_name="log_entries")
    op.drop_table("log_entries")
