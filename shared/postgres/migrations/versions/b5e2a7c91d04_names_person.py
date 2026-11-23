"""flag the locations that name or describe a person

The AI says, for each location it normalizes, whether the text names a person or
describes one. The public views publish only the street of such a location.

Revision ID: b5e2a7c91d04
Revises: f3b8d1a47c92
Create Date: 2026-11-23 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5e2a7c91d04"
down_revision: str | Sequence[str] | None = "f3b8d1a47c92"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "address_normalizations",
        sa.Column(
            "names_person", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("address_normalizations", "names_person")
