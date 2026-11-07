"""add constraints and indexes

Revision ID: 22fc0163d5ff
Revises: k1l2m3n4o5p6
Create Date: 2026-10-31 11:34:29.008029

"""

from collections.abc import Sequence

from alembic import op

revision: str = "22fc0163d5ff"
down_revision: str | Sequence[str] | None = "k1l2m3n4o5p6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("idx_property_llcs_llc_id", "property_llcs", ["llc_id"])
    op.create_foreign_key(
        "fk_planning_documents_civicclerk_event_id",
        "planning_documents",
        "planning_meetings",
        ["civicclerk_event_id"],
        ["civicclerk_event_id"],
    )
    op.create_check_constraint(
        "ck_llcs_lookup_status",
        "llcs",
        "lookup_status IN ('pending', 'in_progress', 'complete', 'error', 'skipped')",
    )
    op.create_check_constraint(
        "ck_budget_documents_document_type",
        "budget_documents",
        "document_type IN ('budget_book', 'line_items')",
    )
    op.create_check_constraint(
        "ck_address_normalizations_geocoded_via",
        "address_normalizations",
        "geocoded_via IN ('manual', 'nominatim')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_address_normalizations_geocoded_via",
        "address_normalizations",
        type_="check",
    )
    op.drop_constraint(
        "ck_budget_documents_document_type", "budget_documents", type_="check"
    )
    op.drop_constraint("ck_llcs_lookup_status", "llcs", type_="check")
    op.drop_constraint(
        "fk_planning_documents_civicclerk_event_id",
        "planning_documents",
        type_="foreignkey",
    )
    op.drop_index("idx_property_llcs_llc_id", table_name="property_llcs")
