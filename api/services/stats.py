from postgres.models.log_entry import LogEntry
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas import HourStat, TypeStat, WeekdayStat

_DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def by_type(db: Session) -> list[TypeStat]:
    rows = db.execute(
        select(LogEntry.incident_type, func.count().label("count"))
        .where(LogEntry.parse_error == False, LogEntry.incident_type.isnot(None))  # noqa: E712
        .group_by(LogEntry.incident_type)
        .order_by(func.count().desc())
        .limit(20)
    ).all()
    return [TypeStat(incident_type=r.incident_type, count=r.count) for r in rows]


def by_hour(db: Session) -> list[HourStat]:
    rows = db.execute(
        select(
            func.extract("hour", LogEntry.reported_at).label("hour"),
            func.count().label("count"),
        )
        .where(LogEntry.parse_error == False, LogEntry.reported_at.isnot(None))  # noqa: E712
        .group_by(func.extract("hour", LogEntry.reported_at))
        .order_by(func.extract("hour", LogEntry.reported_at))
    ).all()
    return [HourStat(hour=int(r.hour), count=r.count) for r in rows]


def by_weekday(db: Session) -> list[WeekdayStat]:
    rows = db.execute(
        select(
            func.extract("dow", LogEntry.reported_at).label("dow"),
            func.count().label("count"),
        )
        .where(LogEntry.parse_error == False, LogEntry.reported_at.isnot(None))  # noqa: E712
        .group_by(func.extract("dow", LogEntry.reported_at))
        .order_by(func.extract("dow", LogEntry.reported_at))
    ).all()
    return [WeekdayStat(day=_DAYS[int(r.dow)], count=r.count) for r in rows]
