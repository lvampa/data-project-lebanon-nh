from decimal import Decimal

from sqlalchemy import Index, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class BudgetCapitalProject(Base):
    __tablename__ = "budget_capital_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    gl_number: Mapped[str] = mapped_column(Text, nullable=False)
    project_name: Mapped[str] = mapped_column(Text, nullable=False)
    fund_code: Mapped[str] = mapped_column(Text, nullable=False)
    fund_name: Mapped[str] = mapped_column(Text, nullable=False)
    year_requested: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    year_approved: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    __table_args__ = (
        UniqueConstraint(
            "fiscal_year", "gl_number", name="uq_budget_capital_project_year_gl"
        ),
        Index("idx_budget_capital_projects_year", "fiscal_year"),
    )
