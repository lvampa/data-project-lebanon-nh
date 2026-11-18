"""build properties from the archive

crawl_runs records each crawl of a source. properties is keyed by `mblu`, the town's
own parcel identifier, with `parcel_id` renamed `vgsi_pid` since it only fetches the
page. Both property tables record the crawl run and the time the archive last saw the
page they came from, and lose their created and updated timestamps. property_llcs is
dropped: the LLC job finds its own owners. `public_properties` is the view the export
reads, so a new column does not reach the site by accident.

Plain schema change. Nothing is live, and `uv run build-properties` rebuilds both
tables, so a database that holds rows in them is emptied here.

Revision ID: c63e9a14d2f8
Revises: b52d8f31c7e4
Create Date: 2026-11-18 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c63e9a14d2f8"
down_revision: str | Sequence[str] | None = "b52d8f31c7e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# What the export reads today. `parcel_id` stays as the name the JSON uses.
_VIEW = """
CREATE VIEW public_properties AS
SELECT
    vgsi_pid AS parcel_id, location, owner, owner_address, land_use,
    lot_size_acres, year_built, building_sqft,
    assessed_land, assessed_building, assessed_total, assessment_year,
    detail_url
FROM properties
"""


def upgrade() -> None:
    op.create_table(
        "crawl_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("pages", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.drop_table("property_llcs")
    op.execute("DELETE FROM property_sales")
    op.execute("DELETE FROM properties")

    op.alter_column("properties", "parcel_id", new_column_name="vgsi_pid")
    op.execute(
        "ALTER TABLE properties"
        " RENAME CONSTRAINT properties_parcel_id_key TO properties_vgsi_pid_key"
    )
    op.alter_column("properties", "mblu", existing_type=sa.Text(), nullable=False)
    op.create_unique_constraint("properties_mblu_key", "properties", ["mblu"])
    for table in ("properties", "property_sales"):
        op.add_column(
            table,
            sa.Column(
                "crawl_run_id",
                sa.Integer(),
                sa.ForeignKey("crawl_runs.id"),
                nullable=False,
            ),
        )
        op.add_column(table, sa.Column("fetched_at", sa.DateTime(), nullable=False))
        op.drop_column(table, "created_at")
    op.drop_column("properties", "updated_at")

    op.execute(_VIEW)


def downgrade() -> None:
    op.execute("DROP VIEW public_properties")
    op.execute("DELETE FROM property_sales")
    op.execute("DELETE FROM properties")

    op.add_column("properties", sa.Column("updated_at", sa.DateTime(), nullable=False))
    for table in ("property_sales", "properties"):
        op.add_column(table, sa.Column("created_at", sa.DateTime(), nullable=False))
        op.drop_column(table, "fetched_at")
        op.drop_column(table, "crawl_run_id")
    op.drop_constraint("properties_mblu_key", "properties", type_="unique")
    op.alter_column("properties", "mblu", existing_type=sa.Text(), nullable=True)
    op.execute(
        "ALTER TABLE properties"
        " RENAME CONSTRAINT properties_vgsi_pid_key TO properties_parcel_id_key"
    )
    op.alter_column("properties", "vgsi_pid", new_column_name="parcel_id")

    op.create_table(
        "property_llcs",
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("llc_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"]),
        sa.ForeignKeyConstraint(["llc_id"], ["llcs.id"]),
        sa.PrimaryKeyConstraint("property_id", "llc_id"),
    )
    op.create_index("idx_property_llcs_llc_id", "property_llcs", ["llc_id"])
    op.drop_table("crawl_runs")
