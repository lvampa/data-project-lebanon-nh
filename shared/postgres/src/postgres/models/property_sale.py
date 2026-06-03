from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class PropertySale(Base):
    __tablename__ = "property_sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(Integer, ForeignKey("properties.id"), nullable=False)
    sale_date: Mapped[date | None] = mapped_column(Date)
    sale_price: Mapped[int | None] = mapped_column(Integer)  # dollars
    grantor: Mapped[str | None] = mapped_column(Text)  # seller
    grantee: Mapped[str | None] = mapped_column(Text)  # buyer
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
