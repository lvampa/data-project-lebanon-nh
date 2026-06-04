from datetime import datetime

from sqlalchemy import DateTime, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class CityStaff(Base):
    __tablename__ = "city_staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    department: Mapped[str] = mapped_column(Text, nullable=False)
    division: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("name", "department", name="uq_city_staff_name_dept"),
        Index("idx_city_staff_department", "department"),
        Index("idx_city_staff_division", "division"),
    )
