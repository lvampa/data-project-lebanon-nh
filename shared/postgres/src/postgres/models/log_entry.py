from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class LogEntry(Base):
    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    case_number: Mapped[str | None] = mapped_column(Text, unique=True)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime)
    call_source: Mapped[str | None] = mapped_column(Text)
    incident_type: Mapped[str | None] = mapped_column(Text)
    disposition: Mapped[str | None] = mapped_column(Text)
    raw_reason_action: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    officer: Mapped[str | None] = mapped_column(Text)
    reference_number: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parse_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_log_entries_reported_at", "reported_at"),
        Index("idx_log_entries_incident_type", "incident_type"),
        Index("idx_log_entries_call_source", "call_source"),
        Index("idx_log_entries_disposition", "disposition"),
    )
