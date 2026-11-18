"""collect the whole VGSI parcel page

properties gains the owner's co-owner, the map/block/lot and account numbers, the
use code, zone and neighborhood, the appraised values, and JSON for the land, building,
outbuilding, extra feature and value history sections. property_sales stores what its
grid prints: owner, price, certificate, book and page, instrument and date. The
seller column goes, since the seller is the owner in the next row down.

Plain schema change. Nothing is live, so no rows are carried over: a database that
holds rows in these tables is reset and scraped again.

Revision ID: b52d8f31c7e4
Revises: a41c7e9d2b60
Create Date: 2026-11-18 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "b52d8f31c7e4"
down_revision: str | Sequence[str] | None = "a41c7e9d2b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TEXT_COLUMNS = (
    "co_owner",
    "mblu",
    "account_number",
    "use_code",
    "zone",
    "neighborhood",
)
_MONEY_COLUMNS = ("appraised_land", "appraised_building", "appraised_total")
_JSON_COLUMNS = ("land", "buildings", "outbuildings", "extra_features", "value_history")


def upgrade() -> None:
    for name in _TEXT_COLUMNS:
        op.add_column("properties", sa.Column(name, sa.Text(), nullable=True))
    for name in _MONEY_COLUMNS:
        op.add_column("properties", sa.Column(name, sa.Integer(), nullable=True))
    for name in _JSON_COLUMNS:
        op.add_column("properties", sa.Column(name, JSONB(), nullable=True))

    op.alter_column("property_sales", "grantee", new_column_name="owner")
    op.drop_column("property_sales", "grantor")
    for name in ("certificate", "book_page", "instrument"):
        op.add_column("property_sales", sa.Column(name, sa.Text(), nullable=True))


def downgrade() -> None:
    for name in ("instrument", "book_page", "certificate"):
        op.drop_column("property_sales", name)
    op.add_column("property_sales", sa.Column("grantor", sa.Text(), nullable=True))
    op.alter_column("property_sales", "owner", new_column_name="grantee")

    for name in (*_JSON_COLUMNS, *_MONEY_COLUMNS, *_TEXT_COLUMNS):
        op.drop_column("properties", name)
