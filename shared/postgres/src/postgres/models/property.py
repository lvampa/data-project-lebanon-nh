from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(primary_key=True)
    parcel_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)  # VGSI map/lot/sub
    location: Mapped[str | None] = mapped_column(Text)  # street address
    owner: Mapped[str | None] = mapped_column(Text)
    owner_address: Mapped[str | None] = mapped_column(Text)
    land_use: Mapped[str | None] = mapped_column(Text)  # e.g. "Single Family"
    lot_size_acres: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    year_built: Mapped[int | None] = mapped_column(Integer)
    building_sqft: Mapped[int | None] = mapped_column(Integer)
    assessed_land: Mapped[int | None] = mapped_column(Integer)  # dollars
    assessed_building: Mapped[int | None] = mapped_column(Integer)
    assessed_total: Mapped[int | None] = mapped_column(Integer)
    assessment_year: Mapped[int | None] = mapped_column(Integer)
    detail_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
