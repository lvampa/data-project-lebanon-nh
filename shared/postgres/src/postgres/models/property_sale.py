from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class PropertySale(Base):
    __tablename__ = "property_sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("properties.id"), nullable=False, index=True
    )
    sale_date: Mapped[date | None] = mapped_column(Date)
    sale_price: Mapped[int | None] = mapped_column(Integer)  # dollars
    # The owner the sale made. The seller is the owner in the next row down.
    owner: Mapped[str | None] = mapped_column(Text)
    certificate: Mapped[str | None] = mapped_column(Text)
    book_page: Mapped[str | None] = mapped_column(Text)
    instrument: Mapped[str | None] = mapped_column(Text)
    crawl_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("crawl_runs.id"), nullable=False
    )
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
