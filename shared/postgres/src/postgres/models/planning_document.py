from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class PlanningDocument(Base):
    __tablename__ = "planning_documents"
    __table_args__ = (Index("idx_planning_documents_event_id", "civicclerk_event_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    civicclerk_file_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    civicclerk_event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str | None] = mapped_column(Text)
    file_type: Mapped[str | None] = mapped_column(Text)
    download_url: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
