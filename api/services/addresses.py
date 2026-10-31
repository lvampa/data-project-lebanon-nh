from datetime import UTC, datetime

import logfire
from postgres.models.address_normalization import AddressNormalization
from postgres.models.log_entry import LogEntry
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from api.deps import Paging
from api.geocoding import geocode_nominatim
from api.schemas import AddressRecord, AddressResult, AddressUpdate, Page


def list_addresses(db: Session, paging: Paging) -> Page[AddressRecord]:
    stmt = (
        select(
            LogEntry.location,
            func.count().label("count"),
            AddressNormalization.normalized_address,
            AddressNormalization.lat,
            AddressNormalization.lng,
        )
        .outerjoin(
            AddressNormalization,
            LogEntry.location == AddressNormalization.raw_address,
        )
        .where(LogEntry.location.isnot(None))
        .group_by(
            LogEntry.location,
            AddressNormalization.normalized_address,
            AddressNormalization.lat,
            AddressNormalization.lng,
        )
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(
        paging.apply(stmt.order_by(func.count().desc(), LogEntry.location))
    ).all()
    return Page[AddressRecord](
        total=total,
        page=paging.page,
        per_page=paging.per_page,
        items=[
            AddressRecord(
                raw_address=r.location,
                count=r.count,
                normalized_address=r.normalized_address,
                lat=r.lat,
                lng=r.lng,
                is_normalized=r.normalized_address is not None,
            )
            for r in rows
        ],
    )


def update_address(
    db: Session,
    raw_address: str,
    update: AddressUpdate,
    *,
    nominatim_contact: str | None,
) -> AddressResult:
    now = datetime.now(UTC).replace(tzinfo=None)
    changes = {
        "normalized_address": update.normalized_address,
        "notes": update.notes,
        "updated_at": now,
        **_new_coordinates(update, nominatim_contact),
    }
    with logfire.span(
        "upsert address normalization {raw_address}", raw_address=raw_address
    ):
        stored = db.execute(
            insert(AddressNormalization)
            .values(raw_address=raw_address, created_at=now, **changes)
            .on_conflict_do_update(index_elements=["raw_address"], set_=changes)
            .returning(
                AddressNormalization.lat,
                AddressNormalization.lng,
                AddressNormalization.geocoded_via,
            )
        ).one()
        db.commit()
    return AddressResult(
        raw_address=raw_address,
        normalized_address=update.normalized_address,
        lat=stored.lat,
        lng=stored.lng,
        geocoded_via=stored.geocoded_via,
    )


def _new_coordinates(update: AddressUpdate, nominatim_contact: str | None) -> dict:
    """Coordinates to write, or {} to keep whatever the row already has."""
    if update.lat is not None:
        return {"lat": update.lat, "lng": update.lng, "geocoded_via": "manual"}
    if update.geocode:
        lat, lng = geocode_nominatim(
            update.normalized_address, contact=nominatim_contact
        )
        if lat is not None:
            return {"lat": lat, "lng": lng, "geocoded_via": "nominatim"}
        logfire.info(
            "geocode miss keeps existing coordinates for {address}",
            address=update.normalized_address,
        )
    return {}
