from datetime import datetime

from sqlalchemy import DateTime, Float, Text
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class AddressNormalization(Base):
    __tablename__ = "address_normalizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_address: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    normalized_address: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    geocoded_via: Mapped[str | None] = mapped_column(Text)  # 'manual' | 'nominatim'
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
