from sqlalchemy import Index, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class BudgetLineItem(Base):
    __tablename__ = "budget_line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    gl_number: Mapped[str] = mapped_column(Text, nullable=False)
    fund_code: Mapped[str] = mapped_column(Text, nullable=False)
    fund_name: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    prior_year_amended: Mapped[float | None] = mapped_column(Numeric(14, 2))
    year_requested: Mapped[float | None] = mapped_column(Numeric(14, 2))
    year_approved: Mapped[float | None] = mapped_column(Numeric(14, 2))

    __table_args__ = (
        UniqueConstraint("fiscal_year", "gl_number", name="uq_budget_line_item_year_gl"),
        Index("idx_budget_line_items_year_dept", "fiscal_year", "department"),
        Index("idx_budget_line_items_year_fund", "fiscal_year", "fund_code"),
    )
