from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from api.deps import get_db
from postgres.models.log_entry import LogEntry

router = APIRouter()
_DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


@router.get("/by-type")
def by_type(db: Annotated[Session, Depends(get_db)]):
    rows = db.execute(
        select(LogEntry.incident_type, func.count().label("count"))
        .where(LogEntry.parse_error == False, LogEntry.incident_type.isnot(None))  # noqa: E712
        .group_by(LogEntry.incident_type)
        .order_by(func.count().desc())
        .limit(20)
    ).all()
    return [{"incident_type": r.incident_type, "count": r.count} for r in rows]


@router.get("/by-hour")
def by_hour(db: Annotated[Session, Depends(get_db)]):
    rows = db.execute(
        select(
            func.extract("hour", LogEntry.reported_at).label("hour"),
            func.count().label("count"),
        )
        .where(LogEntry.parse_error == False, LogEntry.reported_at.isnot(None))  # noqa: E712
        .group_by(func.extract("hour", LogEntry.reported_at))
        .order_by(func.extract("hour", LogEntry.reported_at))
    ).all()
    return [{"hour": int(r.hour), "count": r.count} for r in rows]


@router.get("/by-weekday")
def by_weekday(db: Annotated[Session, Depends(get_db)]):
    rows = db.execute(
        select(
            func.extract("dow", LogEntry.reported_at).label("dow"),
            func.count().label("count"),
        )
        .where(LogEntry.parse_error == False, LogEntry.reported_at.isnot(None))  # noqa: E712
        .group_by(func.extract("dow", LogEntry.reported_at))
        .order_by(func.extract("dow", LogEntry.reported_at))
    ).all()
    return [{"day": _DAYS[int(r.dow)], "count": r.count} for r in rows]
