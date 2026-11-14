from datetime import UTC, datetime
from typing import Any, cast

import logfire
from locations.geocode import geocode, in_city_bounds
from postgres.models.address_normalization import AddressNormalization
from postgres.models.log_entry import LogEntry
from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from api.deps import NormalizationFilter, Paging
from api.schemas import AddressRecord, AddressResult, AddressUpdate, Page
from api.services.normalizations import apply_filter


def list_addresses(
    db: Session, paging: Paging, filters: NormalizationFilter
) -> Page[AddressRecord]:
    columns = (
        AddressNormalization.normalized_address,
        AddressNormalization.kind,
        AddressNormalization.source,
        AddressNormalization.needs_review,
        AddressNormalization.lat,
        AddressNormalization.lng,
    )
    stmt = (
        select(LogEntry.location, func.count().label("count"), *columns)
        .outerjoin(
            AddressNormalization,
            LogEntry.location == AddressNormalization.raw_address,
        )
        .where(LogEntry.location.isnot(None))
        .group_by(LogEntry.location, *columns)
    )
    stmt = apply_filter(
        stmt,
        AddressNormalization.source,
        AddressNormalization.needs_review,
        AddressNormalization.normalized_address,
        filters,
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
                kind=r.kind,
                source=r.source,
                needs_review=bool(r.needs_review),
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
    # A human value has no prompt version. The AI call that came before it stays in
    # ai_call_id, so the AI's answer can be compared with this correction.
    changes = {
        "normalized_address": update.normalized_address,
        "notes": update.notes,
        "source": "human",
        "needs_review": False,
        "prompt_version": None,
        "updated_at": now,
        **_new_coordinates(update, nominatim_contact),
        **({"kind": update.kind} if update.kind else {}),
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
        found = geocode(
            f"{update.normalized_address}, Lebanon, NH, USA", contact=nominatim_contact
        )
        # Coordinates Connor types are accepted anywhere. A lookup that lands outside
        # the city is a miss, such as a street of the same name in another state.
        if found is not None and in_city_bounds(found.lat, found.lng):
            return {
                "lat": found.lat,
                "lng": found.lng,
                "geocoded_via": "nominatim",
                "coordinate_precision": found.precision,
            }
        logfire.info(
            "geocode miss keeps existing coordinates for {address}",
            address=update.normalized_address,
        )
    return {}


def delete_address(db: Session, raw_address: str) -> bool:
    """Hand a value back to AI: its row and its failed attempts go. False if no row."""
    with logfire.span(
        "delete address normalization {raw_address}", raw_address=raw_address
    ):
        result = db.execute(
            delete(AddressNormalization).where(
                AddressNormalization.raw_address == raw_address
            )
        )
        db.commit()
    return cast(CursorResult[Any], result).rowcount > 0
