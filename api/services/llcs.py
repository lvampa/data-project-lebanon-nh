import logfire
from postgres.models.llc import Llc as LlcModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import Paging
from api.schemas import Llc, LookupStatus, Page


def list_llcs(
    db: Session, paging: Paging, lookup_status: LookupStatus | None = None
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


def update_llc_status(
    db: Session, llc_id: int, lookup_status: LookupStatus
) -> LlcModel | None:
    row = db.get(LlcModel, llc_id)
    if row is None:
        logfire.info("llc {llc_id} not found", llc_id=llc_id)
        return None
    with logfire.span(
        "update llc {llc_id} lookup status", llc_id=llc_id, lookup_status=lookup_status
    ):
        row.lookup_status = lookup_status
        db.commit()
        db.refresh(row)
    return row
