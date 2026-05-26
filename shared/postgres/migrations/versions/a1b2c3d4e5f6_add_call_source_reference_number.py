"""add call_source and reference_number to log_entries

Revision ID: a1b2c3d4e5f6
Revises: f025cbf058b6
Create Date: 2026-05-25 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f025cbf058b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("log_entries", sa.Column("call_source", sa.Text(), nullable=True))
    op.add_column("log_entries", sa.Column("reference_number", sa.Text(), nullable=True))
    op.create_index("idx_log_entries_call_source", "log_entries", ["call_source"])
    op.create_index("idx_log_entries_disposition", "log_entries", ["disposition"])


def downgrade() -> None:
    op.drop_index("idx_log_entries_disposition", table_name="log_entries")
    op.drop_index("idx_log_entries_call_source", table_name="log_entries")
    op.drop_column("log_entries", "reference_number")
    op.drop_column("log_entries", "call_source")
