from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from postgres.models.log_entry import LogEntry
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import Incident, IncidentsResponse

router = APIRouter()


@router.get("", response_model=IncidentsResponse)
def list_incidents(
    db: Annotated[Session, Depends(get_db)],
    date_from: date | None = None,
    date_to: date | None = None,
    incident_type: str | None = None,
    disposition: str | None = None,
    officer: str | None = None,
    page: int = 1,
    per_page: int = Query(default=50, le=200),
) -> IncidentsResponse:
    stmt = select(LogEntry).where(LogEntry.parse_error == False)  # noqa: E712
    if date_from:
        stmt = stmt.where(LogEntry.reported_at >= date_from)
    if date_to:
        stmt = stmt.where(LogEntry.reported_at < date_to + timedelta(days=1))
    if incident_type:
        stmt = stmt.where(LogEntry.incident_type.ilike(f"%{incident_type}%"))
    if disposition:
        stmt = stmt.where(LogEntry.disposition.ilike(f"%{disposition}%"))
    if officer:
        stmt = stmt.where(LogEntry.officer.ilike(f"%{officer}%"))

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(
        stmt.order_by(LogEntry.reported_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()

    return IncidentsResponse(
        total=total,
        page=page,
        per_page=per_page,
        items=[Incident.model_validate(r) for r in rows],
    )
