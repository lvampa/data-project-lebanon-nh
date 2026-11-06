from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from postgres.models.llc import Llc as LlcModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.auth import require_admin
from api.deps import Paging, get_db, get_paging
from api.schemas import Llc, LlcStatusUpdate, LookupStatus, Page

router = APIRouter()


@router.get("", response_model=Page[Llc])
def list_llcs(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[Paging, Depends(get_paging)],
    lookup_status: LookupStatus | None = None,
) -> Page[Llc]:
    stmt = select(LlcModel)
    if lookup_status:
        stmt = stmt.where(LlcModel.lookup_status == lookup_status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(paging.apply(stmt.order_by(LlcModel.name))).all()
    return Page[Llc](
        total=total,
        page=paging.page,
        per_page=paging.per_page,
        items=[Llc.model_validate(r) for r in rows],
    )


@router.patch(
    "/{llc_id}/status", response_model=Llc, dependencies=[Depends(require_admin)]
)
def update_llc_status(
    llc_id: int,
    body: LlcStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> Llc:
    row = db.get(LlcModel, llc_id)
    if row is None:
        raise HTTPException(status_code=404, detail="LLC not found")
    row.lookup_status = body.lookup_status
    db.commit()
    db.refresh(row)
    return Llc.model_validate(row)
