from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.auth import require_admin
from api.deps import Paging, get_db, get_paging
from api.schemas import CategoryRecord, CategoryResult, CategoryUpdate, Page
from api.services import categories

router = APIRouter()


@router.get("", response_model=Page[CategoryRecord])
def list_categories(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[Paging, Depends(get_paging)],
) -> Page[CategoryRecord]:
    return categories.list_categories(db, paging)


@router.patch(
    "/{raw_incident_type:path}",
    response_model=CategoryResult,
    dependencies=[Depends(require_admin)],
)
def update_category(
    raw_incident_type: str,
    body: CategoryUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> CategoryResult:
    return categories.update_category(db, raw_incident_type, body)
