"""add properties and property_sales tables

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-03 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "properties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parcel_id", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("owner", sa.Text(), nullable=True),
        sa.Column("owner_address", sa.Text(), nullable=True),
        sa.Column("land_use", sa.Text(), nullable=True),
        sa.Column("lot_size_acres", sa.Numeric(10, 4), nullable=True),
        sa.Column("year_built", sa.Integer(), nullable=True),
        sa.Column("building_sqft", sa.Integer(), nullable=True),
        sa.Column("assessed_land", sa.Integer(), nullable=True),
        sa.Column("assessed_building", sa.Integer(), nullable=True),
        sa.Column("assessed_total", sa.Integer(), nullable=True),
        sa.Column("assessment_year", sa.Integer(), nullable=True),
        sa.Column("detail_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parcel_id"),
    )
    op.create_table(
        "property_sales",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("sale_date", sa.Date(), nullable=True),
        sa.Column("sale_price", sa.Integer(), nullable=True),
        sa.Column("grantor", sa.Text(), nullable=True),
        sa.Column("grantee", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_property_sales_property_id", "property_sales", ["property_id"])


def downgrade() -> None:
    op.drop_index("ix_property_sales_property_id", table_name="property_sales")
    op.drop_table("property_sales")
    op.drop_table("properties")
