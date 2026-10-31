from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from postgres.models.address_normalization import AddressNormalization
from postgres.models.log_entry import LogEntry
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from api.deps import get_db
from api.geocoding import geocode_nominatim
from api.schemas import AddressRecord, AddressResult, AddressUpdate

router = APIRouter()


@router.get("", response_model=list[AddressRecord])
def list_addresses(db: Annotated[Session, Depends(get_db)]) -> list[AddressRecord]:
    rows = db.execute(
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
        .order_by(func.count().desc())
    ).all()
    return [
        AddressRecord(
            raw_address=r.location,
            count=r.count,
            normalized_address=r.normalized_address,
            lat=r.lat,
            lng=r.lng,
            is_normalized=r.normalized_address is not None,
        )
        for r in rows
    ]


@router.patch("/{raw_address:path}", response_model=AddressResult)
def update_address(
    raw_address: str,
    body: AddressUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> AddressResult:
    now = datetime.now(UTC).replace(tzinfo=None)
    changes = {
        "normalized_address": body.normalized_address,
        "notes": body.notes,
        "updated_at": now,
        **_new_coordinates(body),
    }
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
        normalized_address=body.normalized_address,
        lat=stored.lat,
        lng=stored.lng,
        geocoded_via=stored.geocoded_via,
    )


def _new_coordinates(body: AddressUpdate) -> dict:
    """Coordinates to write, or {} to keep whatever the row already has."""
    if body.lat is not None:
        return {"lat": body.lat, "lng": body.lng, "geocoded_via": "manual"}
    if body.geocode:
        lat, lng = geocode_nominatim(body.normalized_address)
        if lat is not None:
            return {"lat": lat, "lng": lng, "geocoded_via": "nominatim"}
    return {}
