from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    Index,
    Integer,
    Text,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column

from postgres.base import Base
from postgres.models.provenance import ProvenanceMixin, source_check


class AddressNormalization(ProvenanceMixin, Base):
    __tablename__ = "address_normalizations"
    __table_args__ = (
        CheckConstraint(
            "geocoded_via IN ('manual', 'nominatim', 'place_code', 'osm', 'research')",
            name="ck_address_normalizations_geocoded_via",
        ),
        CheckConstraint(
            "kind IN ('address', 'intersection', 'place', 'highway')",
            name="ck_address_normalizations_kind",
        ),
        CheckConstraint(
            "coordinate_precision IN ('exact', 'approximate')",
            name="ck_address_normalizations_coordinate_precision",
        ),
        source_check("address_normalizations"),
        Index("idx_address_normalizations_place_code", "place_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_address: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    normalized_address: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str | None] = mapped_column(Text)
    # The place code the log prints, such as `L HANNAF`, when the raw value had one.
    place_code: Mapped[str | None] = mapped_column(Text)
    # The street from the street list that the AI named, in canonical form.
    street: Mapped[str | None] = mapped_column(Text)
    geocode_query: Mapped[str | None] = mapped_column(Text)
    # True when the AI found that the text names a person or describes one. The public
    # views publish only the street of such a location, and of every `human` row.
    names_person: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    # How the coordinates were found. `source` says who owns the row.
    geocoded_via: Mapped[str | None] = mapped_column(Text)
    # The OpenStreetMap feature the pin came from, such as "way/123456", when found there.
    osm_ref: Mapped[str | None] = mapped_column(Text)
    # The page a `research` pin was found on.
    geocode_source_url: Mapped[str | None] = mapped_column(Text)
    # `exact` for a matched address, place or intersection; `approximate` for a street
    # or highway matched without a point on it.
    coordinate_precision: Mapped[str | None] = mapped_column(Text)
    geocode_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # What a geocode retry last looked this row up with, whether it placed the row or not:
    # the snapshot, the place-match prompt, and the row's kind, street and address. The
    # retries skip a row whose mark is what they would write now.
    snapshot_checked: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    # A location that names a person and is not clearly safe is held out of the public data
    # until a person sets `privacy_handled_at`. The public views read both.
    privacy_hold: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    privacy_handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The normalized text, in lowercase, that was handled. A different text is held again.
    privacy_handled_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
