from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from postgres.models.incident_type_category import IncidentTypeCategory
from postgres.models.log_entry import LogEntry
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from api.deps import Paging, get_db, get_paging
from api.schemas import CategoryRecord, CategoryResult, CategoryUpdate, Page

router = APIRouter()


@router.get("", response_model=Page[CategoryRecord])
def list_categories(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[Paging, Depends(get_paging)],
) -> Page[CategoryRecord]:
    stmt = (
        select(
            LogEntry.incident_type,
            func.count().label("count"),
            IncidentTypeCategory.category,
            IncidentTypeCategory.subcategory,
        )
        .outerjoin(
            IncidentTypeCategory,
            LogEntry.incident_type == IncidentTypeCategory.raw_incident_type,
        )
        .where(LogEntry.incident_type.isnot(None))
        .group_by(
            LogEntry.incident_type,
            IncidentTypeCategory.category,
            IncidentTypeCategory.subcategory,
        )
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(
        paging.apply(stmt.order_by(func.count().desc(), LogEntry.incident_type))
    ).all()
    return Page[CategoryRecord](
        total=total,
        page=paging.page,
        per_page=paging.per_page,
        items=[
            CategoryRecord(
                raw_incident_type=r.incident_type,
                count=r.count,
                category=r.category,
                subcategory=r.subcategory,
                is_categorized=r.category is not None,
            )
            for r in rows
        ],
    )


@router.patch("/{raw_incident_type:path}", response_model=CategoryResult)
def update_category(
    raw_incident_type: str,
    body: CategoryUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> CategoryResult:
    now = datetime.now(UTC).replace(tzinfo=None)
    changes = {
        "category": body.category,
        "subcategory": body.subcategory,
        "updated_at": now,
    }
    db.execute(
        insert(IncidentTypeCategory)
        .values(raw_incident_type=raw_incident_type, created_at=now, **changes)
        .on_conflict_do_update(index_elements=["raw_incident_type"], set_=changes)
    )
    db.commit()
    return CategoryResult(
        raw_incident_type=raw_incident_type,
        category=body.category,
        subcategory=body.subcategory,
    )
