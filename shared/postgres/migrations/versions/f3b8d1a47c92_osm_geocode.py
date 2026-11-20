"""let geocoded_via say osm or research, and keep where a pin came from

Revision ID: f3b8d1a47c92
Revises: d74f0b2e8a51
Create Date: 2026-11-20 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3b8d1a47c92"
down_revision: str | Sequence[str] | None = "d74f0b2e8a51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "ck_address_normalizations_geocoded_via"
_TABLE = "address_normalizations"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column("osm_ref", sa.Text(), nullable=True))
    # The page a researched pin was found on, so it can be checked later.
    op.add_column(_TABLE, sa.Column("geocode_source_url", sa.Text(), nullable=True))
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="check")
    op.create_check_constraint(
        _CONSTRAINT,
        _TABLE,
        "geocoded_via IN ('manual', 'nominatim', 'place_code', 'osm', 'research')",
    )


def downgrade() -> None:
    # The pin an osm or research row had before is not kept, so it goes back to waiting
    # for a lookup: no pin, no precision.
    op.execute(
        f"UPDATE {_TABLE} SET lat = NULL, lng = NULL, coordinate_precision = NULL,"
        " geocoded_via = NULL WHERE geocoded_via IN ('osm', 'research')"
    )
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="check")
    op.create_check_constraint(
        _CONSTRAINT, _TABLE, "geocoded_via IN ('manual', 'nominatim', 'place_code')"
    )
    op.drop_column(_TABLE, "geocode_source_url")
    op.drop_column(_TABLE, "osm_ref")
