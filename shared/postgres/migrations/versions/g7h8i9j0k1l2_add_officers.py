"""add city_staff table

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "g7h8i9j0k1l2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "city_staff",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("department", sa.Text(), nullable=False),
        sa.Column("division", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "department", name="uq_city_staff_name_dept"),
    )
    op.create_index("idx_city_staff_department", "city_staff", ["department"])
    op.create_index("idx_city_staff_division", "city_staff", ["division"])


def downgrade() -> None:
    op.drop_index("idx_city_staff_division", table_name="city_staff")
    op.drop_index("idx_city_staff_department", table_name="city_staff")
    op.drop_table("city_staff")
