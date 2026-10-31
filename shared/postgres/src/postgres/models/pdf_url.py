from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class PdfUrl(Base):
    __tablename__ = "pdf_urls"
    __table_args__ = (
        Index("idx_pdf_urls_state_created_at", "state", "created_at"),
        CheckConstraint(
            "state IN ('pending', 'in_progress', 'complete', 'error')",
            name="ck_pdf_urls_state",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    archive_url: Mapped[str | None] = mapped_column(Text)
    log_date: Mapped[date | None] = mapped_column(Date)
    state: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending", server_default="pending"
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)
    entry_count: Mapped[int | None] = mapped_column(Integer)
    raw_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
