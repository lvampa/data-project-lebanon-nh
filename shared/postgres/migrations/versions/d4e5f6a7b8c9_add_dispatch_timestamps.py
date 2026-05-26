"""add dispatch timestamps to log_entries

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-25 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("log_entries", sa.Column("dispatched_at", sa.DateTime(), nullable=True))
    op.add_column("log_entries", sa.Column("enroute_at", sa.DateTime(), nullable=True))
    op.add_column("log_entries", sa.Column("arrived_at", sa.DateTime(), nullable=True))
    op.add_column("log_entries", sa.Column("cleared_at", sa.DateTime(), nullable=True))
    op.add_column("log_entries", sa.Column("response_seconds", sa.Integer(), nullable=True))
    op.add_column("log_entries", sa.Column("scene_seconds", sa.Integer(), nullable=True))


def downgrade() -> None:
    for col in ["scene_seconds", "response_seconds", "cleared_at", "arrived_at", "enroute_at", "dispatched_at"]:
        op.drop_column("log_entries", col)
