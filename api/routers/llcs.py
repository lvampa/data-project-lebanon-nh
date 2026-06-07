from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import Llc, LlcsResponse, LlcStatusUpdate
from postgres.models.llc import Llc as LlcModel

router = APIRouter()


@router.get("", response_model=LlcsResponse)
def list_llcs(
    db: Annotated[Session, Depends(get_db)],
    lookup_status: str | None = None,
) -> LlcsResponse:
    stmt = select(LlcModel)
    if lookup_status:
        stmt = stmt.where(LlcModel.lookup_status == lookup_status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(LlcModel.name)).all()
    return LlcsResponse(total=total, items=[Llc.model_validate(r) for r in rows])


@router.patch("/{llc_id}/status", response_model=Llc)
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
