from datetime import datetime

from sqlalchemy import DateTime, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class Officer(Base):
    __tablename__ = "officers"

    id: Mapped[int] = mapped_column(primary_key=True)
    # unique within Lebanon PD — single-jurisdiction spider, name collisions are not expected
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    rank: Mapped[str | None] = mapped_column(Text)
    division: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (Index("idx_officers_division", "division"),)
