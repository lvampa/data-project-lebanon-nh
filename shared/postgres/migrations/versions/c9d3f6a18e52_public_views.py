"""add the public views the static export reads

`public_locations` and `public_log_entries` are the one place the public rules live: a
location that names or describes a person publishes only its street, and a type shows its
plain name or "Other". The export reads these views and never the tables.

A row is flagged when `names_person` is true, when a person placed it (`source = 'human'`,
a row that `normalize --redo` never revisits, so it never gets the AI's flag), or when it
has no normalized address. The test is in the view, so a row that becomes `human` later is
flagged with no write to remember.

Revision ID: c9d3f6a18e52
Revises: b5e2a7c91d04
Create Date: 2026-11-23 13:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c9d3f6a18e52"
down_revision: str | Sequence[str] | None = "b5e2a7c91d04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# One row per address_normalizations row. A flagged row gives its street as its name, is a
# road, and has no pin of its own: the export hangs its calls on its street's pin.
_PUBLIC_LOCATIONS = """
CREATE VIEW public_locations AS
SELECT
    an.raw_address,
    CASE WHEN flag.flagged THEN an.street ELSE an.normalized_address END
        AS normalized_address,
    CASE WHEN flag.flagged THEN 'road' ELSE an.kind END AS kind,
    an.street,
    flag.flagged AS names_person,
    CASE WHEN flag.flagged THEN NULL ELSE an.lat END AS lat,
    CASE WHEN flag.flagged THEN NULL ELSE an.lng END AS lng,
    CASE WHEN flag.flagged THEN 'approximate' ELSE an.coordinate_precision END
        AS coordinate_precision
FROM address_normalizations an
CROSS JOIN LATERAL (
    SELECT an.names_person
        OR an.source IS NOT DISTINCT FROM 'human'
        OR an.normalized_address IS NULL AS flagged
) flag
"""

# The log's entries with the category from the log's own type, the plain type name, and the
# public location. The log's type text stays in `raw_incident_type` for a place card's
# details, and the log's location text in `raw_location` for the join. No export selects
# `raw_location`.
_PUBLIC_LOG_ENTRIES = """
CREATE VIEW public_log_entries AS
SELECT
    le.id,
    le.case_number,
    le.source_url,
    le.log_date,
    le.reported_at,
    le.call_source,
    call_category(le.incident_type, le.call_source) AS category,
    COALESCE(itc.normalized_type, 'Other') AS incident_type,
    le.incident_type AS raw_incident_type,
    le.disposition,
    le.officer,
    le.reference_number,
    le.dispatched_at,
    le.arrived_at,
    le.cleared_at,
    le.parse_error,
    le.location AS raw_location,
    pl.normalized_address AS location
FROM log_entries le
LEFT JOIN incident_type_categories itc
    ON itc.raw_incident_type = le.incident_type
LEFT JOIN public_locations pl
    ON pl.raw_address = le.location
"""


def upgrade() -> None:
    op.execute(_PUBLIC_LOCATIONS)
    op.execute(_PUBLIC_LOG_ENTRIES)


def downgrade() -> None:
    op.execute("DROP VIEW public_log_entries")
    op.execute("DROP VIEW public_locations")
