"""add normalization provenance and the location columns

Both lookup tables gain `source`, `prompt_version`, `ai_call_id`, `needs_review` and
`failed_attempts`. incident_type_categories swaps `subcategory` for `normalized_type`
and lets `category` be empty while a value waits. address_normalizations gains the
location columns and a `place_code` value for `geocoded_via`.

Rows that exist now were not produced by a rule or by AI, so they become `human` rows,
and a later AI run will not overwrite them.

Revision ID: a41c7e9d2b60
Revises: 7c4d2b19a8e3
Create Date: 2026-11-13 12:00:00.000000

"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "a41c7e9d2b60"
down_revision: str | Sequence[str] | None = "7c4d2b19a8e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCES = "source IN ('rule', 'ai', 'human')"


def _provenance_columns() -> list[sa.Column[Any]]:
    return [
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("ai_call_id", sa.Text(), nullable=True),
        sa.Column("needs_review", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
    ]


_PROVENANCE_NAMES = (
    "source",
    "prompt_version",
    "ai_call_id",
    "needs_review",
    "failed_attempts",
)


def upgrade() -> None:
    _upgrade_incident_type_categories()
    _upgrade_address_normalizations()


def downgrade() -> None:
    _downgrade_address_normalizations()
    _downgrade_incident_type_categories()


def _upgrade_incident_type_categories() -> None:
    table = "incident_type_categories"
    for column in _provenance_columns():
        op.add_column(table, column)
    op.add_column(table, sa.Column("normalized_type", sa.Text(), nullable=True))
    op.alter_column(table, "category", existing_type=sa.Text(), nullable=True)
    op.drop_column(table, "subcategory")
    op.execute(f"UPDATE {table} SET source = 'human' WHERE category IS NOT NULL")
    op.create_check_constraint(f"ck_{table}_source", table, _SOURCES)


def _downgrade_incident_type_categories() -> None:
    table = "incident_type_categories"
    op.drop_constraint(f"ck_{table}_source", table, type_="check")
    # A row with no category is a waiting value, which the old table could not hold.
    op.execute(f"DELETE FROM {table} WHERE category IS NULL")
    op.add_column(table, sa.Column("subcategory", sa.Text(), nullable=True))
    op.alter_column(table, "category", existing_type=sa.Text(), nullable=False)
    op.drop_column(table, "normalized_type")
    for name in _PROVENANCE_NAMES:
        op.drop_column(table, name)


def _upgrade_address_normalizations() -> None:
    table = "address_normalizations"
    for column in _provenance_columns():
        op.add_column(table, column)
    op.add_column(table, sa.Column("kind", sa.Text(), nullable=True))
    op.add_column(table, sa.Column("place_code", sa.Text(), nullable=True))
    op.add_column(table, sa.Column("street", sa.Text(), nullable=True))
    op.add_column(table, sa.Column("geocode_query", sa.Text(), nullable=True))
    op.add_column(table, sa.Column("coordinate_precision", sa.Text(), nullable=True))
    op.add_column(
        table,
        sa.Column("geocode_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index(f"idx_{table}_place_code", table, ["place_code"])
    op.execute(
        f"UPDATE {table} SET source = 'human' WHERE normalized_address IS NOT NULL"
    )

    op.create_check_constraint(f"ck_{table}_source", table, _SOURCES)
    op.create_check_constraint(
        f"ck_{table}_kind",
        table,
        "kind IN ('address', 'intersection', 'place', 'highway')",
    )
    op.create_check_constraint(
        f"ck_{table}_coordinate_precision",
        table,
        "coordinate_precision IN ('exact', 'approximate')",
    )
    op.drop_constraint(f"ck_{table}_geocoded_via", table, type_="check")
    op.create_check_constraint(
        f"ck_{table}_geocoded_via",
        table,
        "geocoded_via IN ('manual', 'nominatim', 'place_code')",
    )


def _downgrade_address_normalizations() -> None:
    table = "address_normalizations"
    op.drop_constraint(f"ck_{table}_geocoded_via", table, type_="check")
    # The old check has no place_code, so those coordinates fall back to nominatim.
    op.execute(
        f"UPDATE {table} SET geocoded_via = 'nominatim' WHERE geocoded_via = 'place_code'"
    )
    op.create_check_constraint(
        f"ck_{table}_geocoded_via", table, "geocoded_via IN ('manual', 'nominatim')"
    )
    op.drop_constraint(f"ck_{table}_coordinate_precision", table, type_="check")
    op.drop_constraint(f"ck_{table}_kind", table, type_="check")
    op.drop_constraint(f"ck_{table}_source", table, type_="check")
    op.drop_index(f"idx_{table}_place_code", table_name=table)
    for name in (
        "geocode_attempts",
        "coordinate_precision",
        "geocode_query",
        "street",
        "place_code",
        "kind",
        *_PROVENANCE_NAMES,
    ):
        op.drop_column(table, name)
