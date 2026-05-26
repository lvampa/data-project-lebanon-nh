from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from api.deps import get_db
from api.geocoding import geocode_nominatim
from postgres.models.address_normalization import AddressNormalization
from postgres.models.log_entry import LogEntry

router = APIRouter()


class AddressUpdate(BaseModel):
    normalized_address: str
    notes: str | None = None
    geocode: bool = True


@router.get("")
def list_addresses(db: Annotated[Session, Depends(get_db)]):
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
        {
            "raw_address": r.location,
            "count": r.count,
            "normalized_address": r.normalized_address,
            "lat": r.lat,
            "lng": r.lng,
            "is_normalized": r.normalized_address is not None,
        }
        for r in rows
    ]


@router.patch("/{raw_address:path}")
def update_address(
    raw_address: str,
    body: AddressUpdate,
    db: Annotated[Session, Depends(get_db)],
):
    lat, lng, geocoded_via = None, None, "manual"
    if body.geocode:
        lat, lng = geocode_nominatim(body.normalized_address)
        if lat is not None:
            geocoded_via = "nominatim"

    now = datetime.now(timezone.utc)
    existing = db.scalar(
        select(AddressNormalization).where(
            AddressNormalization.raw_address == raw_address
        )
    )
    if existing:
        existing.normalized_address = body.normalized_address
        existing.lat = lat
        existing.lng = lng
        existing.geocoded_via = geocoded_via
        existing.notes = body.notes
        existing.updated_at = now
    else:
        db.add(
            AddressNormalization(
                raw_address=raw_address,
                normalized_address=body.normalized_address,
                lat=lat,
                lng=lng,
                geocoded_via=geocoded_via,
                notes=body.notes,
                created_at=now,
                updated_at=now,
            )
        )
    db.commit()
    return {
        "raw_address": raw_address,
        "normalized_address": body.normalized_address,
        "lat": lat,
        "lng": lng,
        "geocoded_via": geocoded_via,
    }
