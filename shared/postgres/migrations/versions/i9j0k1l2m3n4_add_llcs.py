"""add llcs and property_llcs tables

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-06-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llcs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("raw_owner_name", sa.Text(), nullable=True),
        sa.Column("lookup_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("nh_business_id", sa.Text(), nullable=True),
        sa.Column("business_status", sa.Text(), nullable=True),
        sa.Column("formation_date", sa.Date(), nullable=True),
        sa.Column("business_email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("registered_agent", sa.Text(), nullable=True),
        sa.Column("registered_agent_address", sa.Text(), nullable=True),
        sa.Column("principals", JSONB(), nullable=True),
        sa.Column("last_looked_up_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("idx_llcs_lookup_status", "llcs", ["lookup_status"])

    op.create_table(
        "property_llcs",
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("llc_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"]),
        sa.ForeignKeyConstraint(["llc_id"], ["llcs.id"]),
        sa.PrimaryKeyConstraint("property_id", "llc_id"),
    )


def downgrade() -> None:
    op.drop_table("property_llcs")
    op.drop_index("idx_llcs_lookup_status", table_name="llcs")
    op.drop_table("llcs")
