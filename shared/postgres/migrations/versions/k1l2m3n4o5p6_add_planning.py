"""add planning_meetings and planning_documents tables

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-06-08
"""
import sqlalchemy as sa
from alembic import op

revision = "k1l2m3n4o5p6"
down_revision = "j0k1l2m3n4o5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "planning_meetings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("civicclerk_event_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("meeting_date", sa.DateTime(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("civicclerk_event_id"),
    )
    op.create_index("idx_planning_meetings_meeting_date", "planning_meetings", ["meeting_date"])
    op.create_index("idx_planning_meetings_category", "planning_meetings", ["category"])

    op.create_table(
        "planning_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("civicclerk_file_id", sa.Integer(), nullable=False),
        sa.Column("civicclerk_event_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=True),
        sa.Column("file_type", sa.Text(), nullable=True),
        sa.Column("download_url", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("civicclerk_file_id"),
    )
    op.create_index(
        "idx_planning_documents_event_id", "planning_documents", ["civicclerk_event_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_planning_documents_event_id", table_name="planning_documents")
    op.drop_table("planning_documents")
    op.drop_index("idx_planning_meetings_category", table_name="planning_meetings")
    op.drop_index("idx_planning_meetings_meeting_date", table_name="planning_meetings")
    op.drop_table("planning_meetings")
