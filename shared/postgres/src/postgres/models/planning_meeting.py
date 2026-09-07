from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class PlanningMeeting(Base):
    __tablename__ = "planning_meetings"
    __table_args__ = (
        Index("idx_planning_meetings_meeting_date", "meeting_date"),
        Index("idx_planning_meetings_category", "category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    civicclerk_event_id: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False
    )
    title: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    meeting_date: Mapped[datetime | None] = mapped_column(DateTime)
    location: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
