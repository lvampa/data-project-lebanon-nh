from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class BudgetDocument(Base):
    __tablename__ = "budget_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    document_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    text_extracted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    scraped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "fiscal_year", "document_type", name="uq_budget_document_year_type"
        ),
        CheckConstraint(
            "document_type IN ('budget_book', 'line_items')",
            name="ck_budget_documents_document_type",
        ),
    )
