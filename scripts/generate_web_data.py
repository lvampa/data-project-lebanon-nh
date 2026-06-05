"""Generate static JSON data files for the Next.js frontend.

Run from the repo root:
    uv run python scripts/generate_web_data.py

Writes to web/public/data/:
    stats.json      — totals, by-type counts, by-weekday counts
    incidents.json  — most recent 2000 incidents
    addresses.json  — geocoded incident locations with counts
    staff.json      — city staff (police, fire, clerk, council)
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from postgres import SessionLocal
from postgres.models.address_normalization import AddressNormalization
from postgres.models.city_staff import CityStaff
from postgres.models.log_entry import LogEntry

OUT_DIR = Path(__file__).parent.parent / "web" / "public" / "data"

_DAYS = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}


def format_incidents(rows: list) -> list[dict]:
    return [
        {
            "case_number": r.case_number,
            "reported_at": r.reported_at.isoformat() if r.reported_at else None,
            "call_source": r.call_source,
            "incident_type": r.incident_type,
            "disposition": r.disposition,
            "location": r.location,
            "officer": r.officer,
            "reference_number": r.reference_number,
            "source_url": r.source_url,
        }
        for r in rows
    ]


def format_addresses(rows: list) -> list[dict]:
    return [
        {
            "raw_address": r.location,
            "normalized_address": r.normalized_address,
            "count": r.count,
            "lat": r.lat,
            "lng": r.lng,
        }
        for r in rows
        if r.lat is not None and r.lng is not None
    ]


def format_staff(rows: list) -> list[dict]:
    return [
        {
            "id": r.id,
            "name": r.name,
            "title": r.title,
            "department": r.department,
            "division": r.division,
            "email": r.email,
            "phone": r.phone,
            "source_url": r.source_url,
        }
        for r in rows
    ]


def format_stats(by_type_rows: list, by_weekday_rows: list, total: int) -> dict:
    return {
        "total": total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "by_type": [
            {"incident_type": r.incident_type, "count": r.count}
            for r in by_type_rows
        ],
        "by_weekday": [
            {"day": _DAYS[int(r.dow)], "count": r.count}
            for r in by_weekday_rows
        ],
    }


def _write(filename: str, data: object) -> None:
    path = OUT_DIR / filename
    path.write_text(json.dumps(data, default=str), encoding="utf-8")
    print(f"  wrote {path} ({path.stat().st_size:,} bytes)")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    db: Session = SessionLocal()
    try:
        print("Generating web data...")

        total = db.scalar(
            select(func.count()).select_from(LogEntry).where(LogEntry.parse_error == False)  # noqa: E712
        ) or 0

        by_type_rows = db.execute(
            select(LogEntry.incident_type, func.count().label("count"))
            .where(LogEntry.parse_error == False, LogEntry.incident_type.isnot(None))  # noqa: E712
            .group_by(LogEntry.incident_type)
            .order_by(func.count().desc())
            .limit(20)
        ).all()

        by_weekday_rows = db.execute(
            select(
                func.extract("dow", LogEntry.reported_at).label("dow"),
                func.count().label("count"),
            )
            .where(LogEntry.parse_error == False, LogEntry.reported_at.isnot(None))  # noqa: E712
            .group_by(func.extract("dow", LogEntry.reported_at))
            .order_by(func.extract("dow", LogEntry.reported_at))
        ).all()

        incident_rows = db.scalars(
            select(LogEntry)
            .where(LogEntry.parse_error == False)  # noqa: E712
            .order_by(LogEntry.reported_at.desc())
            .limit(2000)
        ).all()

        address_rows = db.execute(
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

        staff_rows = db.scalars(
            select(CityStaff).order_by(
                CityStaff.department, CityStaff.division, CityStaff.name
            )
        ).all()

        _write("stats.json", format_stats(by_type_rows, by_weekday_rows, total))
        _write("incidents.json", format_incidents(incident_rows))
        _write("addresses.json", format_addresses(address_rows))
        _write("staff.json", format_staff(staff_rows))

        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
