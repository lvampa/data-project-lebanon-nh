from datetime import datetime

from sqlalchemy import DateTime, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class IncidentTypeCategory(Base):
    __tablename__ = "incident_type_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_incident_type: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    subcategory: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (Index("idx_incident_type_categories_category", "category"),)
