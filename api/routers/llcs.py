from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import require_admin
from api.deps import Paging, get_db, get_paging
from api.schemas import Llc, LlcStatusUpdate, LookupStatus, Page
from api.services import llcs

router = APIRouter()


@router.get("", response_model=Page[Llc])
def list_llcs(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[Paging, Depends(get_paging)],
    lookup_status: LookupStatus | None = None,
) -> Page[Llc]:
    return llcs.list_llcs(db, paging, lookup_status)


@router.patch(
    "/{llc_id}/status", response_model=Llc, dependencies=[Depends(require_admin)]
)
def update_llc_status(
    llc_id: int,
    body: LlcStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> Llc:
    row = llcs.update_llc_status(db, llc_id, body.lookup_status)
    if row is None:
        raise HTTPException(status_code=404, detail="LLC not found")
    return Llc.model_validate(row)
