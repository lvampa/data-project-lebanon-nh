"""hold a location out of the public data until a person has handled it

`privacy_hold` marks a location that names a person and is not clearly safe. While it is
held (`privacy_hold` and `privacy_handled_at IS NULL`) the public views treat the location
as unmapped: no name, no street, no pin. Its log entries stay, with no location, and still
count in the totals. Setting `privacy_handled_at` releases it, and it then publishes as any
flagged location does, as its street only.

The two views are replaced, since a view cannot change its expressions in place.

Revision ID: e2f5b9c83d46
Revises: d1e4a8b72c35
Create Date: 2026-11-24 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2f5b9c83d46"
down_revision: str | Sequence[str] | None = "d1e4a8b72c35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The same view as before, with `held` read first. A held row has no name, street or pin, and
# is not flagged, so the export treats it like a location with no coordinates.
_HELD = "(an.privacy_hold AND an.privacy_handled_at IS NULL)"

_PUBLIC_LOCATIONS = f"""
CREATE VIEW public_locations AS
SELECT
    an.raw_address,
    CASE
        WHEN {_HELD} THEN NULL
        WHEN flag.flagged THEN street_pin.normalized_address
        ELSE an.normalized_address
    END AS normalized_address,
    CASE
        WHEN {_HELD} THEN NULL
        WHEN flag.flagged THEN 'road'
        ELSE an.kind
    END AS kind,
    CASE WHEN {_HELD} THEN NULL ELSE an.street END AS street,
    flag.flagged AND NOT {_HELD} AS names_person,
    CASE WHEN flag.flagged OR {_HELD} THEN NULL ELSE an.lat END AS lat,
    CASE WHEN flag.flagged OR {_HELD} THEN NULL ELSE an.lng END AS lng,
    CASE
        WHEN flag.flagged OR {_HELD} THEN 'approximate'
        ELSE an.coordinate_precision
    END AS coordinate_precision
FROM address_normalizations an
CROSS JOIN LATERAL (
    SELECT an.names_person
        OR an.source IS NOT DISTINCT FROM 'human'
        OR an.normalized_address IS NULL AS flagged
) flag
LEFT JOIN LATERAL (
    SELECT bare.normalized_address
    FROM address_normalizations bare
    WHERE flag.flagged
      AND NOT {_HELD}
      AND an.street IS NOT NULL
      AND bare.street = an.street
      AND bare.normalized_address IS NOT NULL
      AND bare.kind NOT IN ('intersection', 'highway')
      AND strpos(bare.normalized_address, ', ') = 0
      AND bare.normalized_address !~ '^\\d'
      AND NOT bare.names_person
      AND bare.source IS DISTINCT FROM 'human'
    ORDER BY (
        SELECT COUNT(*)
        FROM log_entries calls
        JOIN address_normalizations spelling ON spelling.raw_address = calls.location
        WHERE spelling.normalized_address = bare.normalized_address
          AND calls.parse_error = false
    ) DESC, bare.normalized_address
    LIMIT 1
) street_pin ON true
"""

# The old definition, for the downgrade.
_OLD_PUBLIC_LOCATIONS = """
CREATE VIEW public_locations AS
SELECT
    an.raw_address,
    CASE WHEN flag.flagged THEN street_pin.normalized_address ELSE an.normalized_address END
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
LEFT JOIN LATERAL (
    SELECT bare.normalized_address
    FROM address_normalizations bare
    WHERE flag.flagged
      AND an.street IS NOT NULL
      AND bare.street = an.street
      AND bare.normalized_address IS NOT NULL
      AND bare.kind NOT IN ('intersection', 'highway')
      AND strpos(bare.normalized_address, ', ') = 0
      AND bare.normalized_address !~ '^\\d'
      AND NOT bare.names_person
      AND bare.source IS DISTINCT FROM 'human'
    ORDER BY (
        SELECT COUNT(*)
        FROM log_entries calls
        JOIN address_normalizations spelling ON spelling.raw_address = calls.location
        WHERE spelling.normalized_address = bare.normalized_address
          AND calls.parse_error = false
    ) DESC, bare.normalized_address
    LIMIT 1
) street_pin ON true
"""

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
    op.execute("DROP VIEW public_log_entries")
    op.execute("DROP VIEW public_locations")
    op.add_column(
        "address_normalizations",
        sa.Column(
            "privacy_hold", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "address_normalizations",
        sa.Column("privacy_handled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(_PUBLIC_LOCATIONS)
    op.execute(_PUBLIC_LOG_ENTRIES)


def downgrade() -> None:
    op.execute("DROP VIEW public_log_entries")
    op.execute("DROP VIEW public_locations")
    op.drop_column("address_normalizations", "privacy_handled_at")
    op.drop_column("address_normalizations", "privacy_hold")
    op.execute(_OLD_PUBLIC_LOCATIONS)
    op.execute(_PUBLIC_LOG_ENTRIES)
