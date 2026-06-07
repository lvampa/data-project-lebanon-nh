"""
Queries PostgreSQL and writes static JSON files to frontend/web/public/data/.
Run from data-project/: uv run python scrapers/scripts/generate_report.py
"""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import logfire
from dotenv import load_dotenv

load_dotenv()

from postgres import SessionLocal
from postgres.models.address_normalization import AddressNormalization
from postgres.models.incident_type_category import IncidentTypeCategory
from postgres.models.log_entry import LogEntry
from sqlalchemy import func, select

OUTPUT_DIR = (
    Path(__file__).parent.parent.parent / "frontend" / "web" / "public" / "data"
)


def _json_default(obj: object) -> str:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")


def _write(name: str, data: object) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / name
    path.write_text(json.dumps(data, default=_json_default, indent=2))
    logfire.info(
        "wrote {name}",
        name=name,
        bytes=path.stat().st_size,
        records=len(data) if isinstance(data, list) else None,
    )


def generate() -> None:
    logfire.configure()
    with logfire.span("generate report"):
        db = SessionLocal()
        try:
            _write_summary(db)
            _write_incidents(db)
        finally:
            db.close()


def _write_summary(db) -> None:
    total = db.scalar(
        select(func.count()).select_from(
            select(LogEntry).where(LogEntry.parse_error == False).subquery()  # noqa: E712
        )
    )
    date_min = db.scalar(
        select(func.min(LogEntry.reported_at)).where(LogEntry.parse_error == False)  # noqa: E712
    )
    date_max = db.scalar(
        select(func.max(LogEntry.reported_at)).where(LogEntry.parse_error == False)  # noqa: E712
    )
    _write(
        "summary.json",
        {
            "total_incidents": total,
            "date_min": date_min,
            "date_max": date_max,
            "generated_at": datetime.now(UTC),
        },
    )


def _write_incidents(db) -> None:
    cutoff = date.today() - timedelta(days=365)
    rows = db.execute(
        select(
            LogEntry.case_number,
            LogEntry.reported_at,
            LogEntry.incident_type,
            LogEntry.disposition,
            LogEntry.call_source,
            LogEntry.officer,
            LogEntry.location,
            LogEntry.source_url,
            LogEntry.response_seconds,
            LogEntry.scene_seconds,
            AddressNormalization.normalized_address,
            AddressNormalization.lat,
            AddressNormalization.lng,
            IncidentTypeCategory.category,
            IncidentTypeCategory.subcategory,
        )
        .outerjoin(
            AddressNormalization,
            LogEntry.location == AddressNormalization.raw_address,
        )
        .outerjoin(
            IncidentTypeCategory,
            LogEntry.incident_type == IncidentTypeCategory.raw_incident_type,
        )
        .where(
            LogEntry.parse_error == False,  # noqa: E712
            LogEntry.reported_at >= cutoff,
        )
        .order_by(LogEntry.reported_at.desc())
    ).all()

    _write(
        "incidents.json",
        [
            {
                "case_number": r.case_number,
                "reported_at": r.reported_at,
                "incident_type": r.incident_type,
                "disposition": r.disposition,
                "call_source": r.call_source,
                "officer": r.officer,
                "location": r.location,
                "normalized_address": r.normalized_address,
                "lat": r.lat,
                "lng": r.lng,
                "source_url": r.source_url,
                "category": r.category,
                "subcategory": r.subcategory,
                "response_seconds": r.response_seconds,
                "scene_seconds": r.scene_seconds,
            }
            for r in rows
        ],
    )


if __name__ == "__main__":
    generate()
