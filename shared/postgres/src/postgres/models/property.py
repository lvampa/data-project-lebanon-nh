from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The town's own parcel identifier, as other town records print it. Condo units
    # have one each.
    mblu: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # Only for fetching the page. VGSI can renumber it.
    vgsi_pid: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    location: Mapped[str | None] = mapped_column(Text)  # street address
    owner: Mapped[str | None] = mapped_column(Text)
    co_owner: Mapped[str | None] = mapped_column(Text)
    # The owner's mailing address.
    owner_address: Mapped[str | None] = mapped_column(Text)
    account_number: Mapped[str | None] = mapped_column(Text)
    use_code: Mapped[str | None] = mapped_column(Text)
    land_use: Mapped[str | None] = mapped_column(Text)  # the use code's description
    zone: Mapped[str | None] = mapped_column(Text)
    neighborhood: Mapped[str | None] = mapped_column(Text)
    lot_size_acres: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    year_built: Mapped[int | None] = mapped_column(Integer)
    building_sqft: Mapped[int | None] = mapped_column(Integer)
    assessed_land: Mapped[int | None] = mapped_column(Integer)  # dollars
    assessed_building: Mapped[int | None] = mapped_column(Integer)
    assessed_total: Mapped[int | None] = mapped_column(Integer)
    assessment_year: Mapped[int | None] = mapped_column(Integer)
    appraised_land: Mapped[int | None] = mapped_column(Integer)
    appraised_building: Mapped[int | None] = mapped_column(Integer)
    appraised_total: Mapped[int | None] = mapped_column(Integer)
    # Whatever else the parcel page lists, as it prints it. Values stay strings.
    land: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    buildings: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    outbuildings: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    extra_features: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    value_history: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    detail_url: Mapped[str | None] = mapped_column(Text)
    crawl_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("crawl_runs.id"), nullable=False
    )
    # When the archive last saw the page this row was built from.
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
