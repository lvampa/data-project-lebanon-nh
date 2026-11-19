"""add call_category, the kind of a police call

The map groups calls into traffic, police checks, alarms, paperwork and everything
else, which it calls premises. The function is the one place that decides, so every
query that needs a category asks it and the lists below exist once.

Revision ID: d74f0b2e8a51
Revises: c63e9a14d2f8
Create Date: 2026-11-19 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d74f0b2e8a51"
down_revision: str | Sequence[str] | None = "c63e9a14d2f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Each category is tried in this order, and a type is in the first one that matches.
# Every pattern is a prefix or a word to find, matched in any case. Traffic: the
# location names a landmark, but these events happened on the road. Parking lot types
# stay with the place on purpose, because the lot belongs to the business.
_FUNCTION = """
CREATE FUNCTION call_category(incident_type text, call_source text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN incident_type ILIKE ANY (ARRAY[
            'Motor Vehicle Stop%',
            'MV Complaint%',
            'Assist Motorist%',
            'MVA Roadway%',
            'Equip Failure Traffic Light%',
            'Road Hazard%',
            'Parking in Roadway%',
            'Detail Crosswalk%',
            'Detail Traffic Control%'
        ]) THEN 'traffic'
        WHEN incident_type ILIKE ANY (ARRAY[
            'BUSINESS CHECK%',
            'Directed Patrol%',
            'FOOT PATROL%'
        ]) THEN 'checks'
        WHEN incident_type ILIKE '%alarm%' OR call_source = 'Alarm System'
            THEN 'alarms'
        WHEN incident_type ILIKE ANY (ARRAY[
            'Paperwork%',
            'Fingerprint%',
            '%Subpoena%',
            'Records%'
        ]) THEN 'admin'
        ELSE 'premises'
    END
$$
"""


def upgrade() -> None:
    op.execute(_FUNCTION)


def downgrade() -> None:
    op.execute("DROP FUNCTION call_category(text, text)")
