"""add budget tables

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-06-07
"""
import sqlalchemy as sa
from alembic import op

revision = "j0k1l2m3n4o5"
down_revision = "i9j0k1l2m3n4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budget_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("text_extracted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fiscal_year", "document_type", name="uq_budget_document_year_type"),
    )
    op.create_table(
        "budget_line_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("gl_number", sa.Text(), nullable=False),
        sa.Column("fund_code", sa.Text(), nullable=False),
        sa.Column("fund_name", sa.Text(), nullable=False),
        sa.Column("department", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("prior_year_amended", sa.Numeric(14, 2), nullable=True),
        sa.Column("year_requested", sa.Numeric(14, 2), nullable=True),
        sa.Column("year_approved", sa.Numeric(14, 2), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fiscal_year", "gl_number", name="uq_budget_line_item_year_gl"),
    )
    op.create_index("idx_budget_line_items_year_dept", "budget_line_items", ["fiscal_year", "department"])
    op.create_index("idx_budget_line_items_year_fund", "budget_line_items", ["fiscal_year", "fund_code"])
    op.create_table(
        "budget_capital_projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("gl_number", sa.Text(), nullable=False),
        sa.Column("project_name", sa.Text(), nullable=False),
        sa.Column("fund_code", sa.Text(), nullable=False),
        sa.Column("fund_name", sa.Text(), nullable=False),
        sa.Column("year_requested", sa.Numeric(14, 2), nullable=True),
        sa.Column("year_approved", sa.Numeric(14, 2), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fiscal_year", "gl_number", name="uq_budget_capital_project_year_gl"),
    )
    op.create_index("idx_budget_capital_projects_year", "budget_capital_projects", ["fiscal_year"])


def downgrade() -> None:
    op.drop_index("idx_budget_capital_projects_year", table_name="budget_capital_projects")
    op.drop_table("budget_capital_projects")
    op.drop_index("idx_budget_line_items_year_fund", table_name="budget_line_items")
    op.drop_index("idx_budget_line_items_year_dept", table_name="budget_line_items")
    op.drop_table("budget_line_items")
    op.drop_table("budget_documents")
