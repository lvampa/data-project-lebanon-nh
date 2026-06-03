"""add properties and property_sales tables

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-03 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "properties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parcel_id", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("owner", sa.String(), nullable=True),
        sa.Column("owner_address", sa.String(), nullable=True),
        sa.Column("land_use", sa.String(), nullable=True),
        sa.Column("lot_size_acres", sa.Numeric(10, 4), nullable=True),
        sa.Column("year_built", sa.Integer(), nullable=True),
        sa.Column("building_sqft", sa.Integer(), nullable=True),
        sa.Column("assessed_land", sa.Integer(), nullable=True),
        sa.Column("assessed_building", sa.Integer(), nullable=True),
        sa.Column("assessed_total", sa.Integer(), nullable=True),
        sa.Column("assessment_year", sa.Integer(), nullable=True),
        sa.Column("detail_url", sa.String(), nullable=True),
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
        sa.Column("grantor", sa.String(), nullable=True),
        sa.Column("grantee", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("property_sales")
    op.drop_table("properties")
