from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class LogEntry(Base):
    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    case_number: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime)
    call_source: Mapped[str | None] = mapped_column(Text)
    incident_type: Mapped[str | None] = mapped_column(Text)
    disposition: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    place_code: Mapped[str | None] = mapped_column(Text)
    officer: Mapped[str | None] = mapped_column(Text)
    reference_number: Mapped[str | None] = mapped_column(Text)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime)
    enroute_at: Mapped[datetime | None] = mapped_column(DateTime)
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime)
    response_seconds: Mapped[int | None] = mapped_column(Integer)
    scene_seconds: Mapped[int | None] = mapped_column(Integer)
    parse_error: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    disposition_unmatched: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    missing_from_parse: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Moves only when a parsed value changes, not on every reprocess.
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_log_entries_reported_at", "reported_at"),
        Index("idx_log_entries_log_date", "log_date"),
        Index("idx_log_entries_incident_type", "incident_type"),
        Index("idx_log_entries_call_source", "call_source"),
        Index("idx_log_entries_disposition", "disposition"),
    )
