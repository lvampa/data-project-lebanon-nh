from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base


class Llc(Base):
    __tablename__ = "llcs"
    __table_args__ = (Index("idx_llcs_lookup_status", "lookup_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    raw_owner_name: Mapped[str | None] = mapped_column(Text)
    lookup_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending", server_default="pending"
    )
    nh_business_id: Mapped[str | None] = mapped_column(Text)
    business_status: Mapped[str | None] = mapped_column(Text)
    formation_date: Mapped[date | None] = mapped_column(Date)
    business_email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    registered_agent: Mapped[str | None] = mapped_column(Text)
    registered_agent_address: Mapped[str | None] = mapped_column(Text)
    principals: Mapped[list | None] = mapped_column(JSONB)
    last_looked_up_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PropertyLlc(Base):
    __tablename__ = "property_llcs"

    property_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("properties.id"), primary_key=True
    )
    llc_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("llcs.id"), primary_key=True
    )
