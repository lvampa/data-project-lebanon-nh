from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from postgres.models.log_entry import LogEntry
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import Paging, get_db, get_paging
from api.schemas import Incident, Page

router = APIRouter()


@router.get("", response_model=Page[Incident])
def list_incidents(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[Paging, Depends(get_paging)],
    date_from: date | None = None,
    date_to: date | None = None,
    incident_type: str | None = None,
    disposition: str | None = None,
    officer: str | None = None,
) -> Page[Incident]:
    stmt = select(LogEntry).where(LogEntry.parse_error == False)  # noqa: E712
    if date_from:
        stmt = stmt.where(LogEntry.reported_at >= date_from)
    if date_to:
        stmt = stmt.where(LogEntry.reported_at < date_to + timedelta(days=1))
    if incident_type:
        stmt = stmt.where(
            LogEntry.incident_type.icontains(incident_type, autoescape=True)
        )
    if disposition:
        stmt = stmt.where(LogEntry.disposition.icontains(disposition, autoescape=True))
    if officer:
        stmt = stmt.where(LogEntry.officer.icontains(officer, autoescape=True))

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(
        paging.apply(
            stmt.order_by(LogEntry.reported_at.desc().nulls_last(), LogEntry.id.desc())
        )
    ).all()

    return Page[Incident](
        total=total,
        page=paging.page,
        per_page=paging.per_page,
        items=[Incident.model_validate(r) for r in rows],
    )
