from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from api.auth import require_admin
from api.deps import (
    NormalizationFilter,
    Paging,
    get_db,
    get_normalization_filter,
    get_paging,
)
from api.schemas import CategoryRecord, CategoryResult, CategoryUpdate, Page
from api.services import categories

router = APIRouter()


@router.get("", response_model=Page[CategoryRecord])
def list_categories(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[Paging, Depends(get_paging)],
    filters: Annotated[NormalizationFilter, Depends(get_normalization_filter)],
) -> Page[CategoryRecord]:
    return categories.list_categories(db, paging, filters)


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


@router.delete(
    "/{raw_incident_type:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_category(
    raw_incident_type: str, db: Annotated[Session, Depends(get_db)]
) -> Response:
    if not categories.delete_category(db, raw_incident_type):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No normalization for that value"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
