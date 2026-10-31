from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import Paging, get_db, get_paging
from api.schemas import Incident, Page
from api.services import incidents

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
    return incidents.list_incidents(
        db,
        paging,
        date_from=date_from,
        date_to=date_to,
        incident_type=incident_type,
        disposition=disposition,
        officer=officer,
    )
