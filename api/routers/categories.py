from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from postgres.models.incident_type_category import IncidentTypeCategory
from postgres.models.log_entry import LogEntry
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import CategoryRecord, CategoryResult, CategoryUpdate

router = APIRouter()


@router.get("", response_model=list[CategoryRecord])
def list_categories(db: Annotated[Session, Depends(get_db)]) -> list[CategoryRecord]:
    rows = db.execute(
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
        .order_by(func.count().desc())
    ).all()
    return [
        CategoryRecord(
            raw_incident_type=r.incident_type,
            count=r.count,
            category=r.category,
            subcategory=r.subcategory,
            is_categorized=r.category is not None,
        )
        for r in rows
    ]


@router.patch("/{raw_incident_type:path}", response_model=CategoryResult)
def update_category(
    raw_incident_type: str,
    body: CategoryUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> CategoryResult:
    now = datetime.now(UTC).replace(tzinfo=None)
    existing = db.scalar(
        select(IncidentTypeCategory).where(
            IncidentTypeCategory.raw_incident_type == raw_incident_type
        )
    )
    if existing:
        existing.category = body.category
        existing.subcategory = body.subcategory
        existing.updated_at = now
    else:
        db.add(
            IncidentTypeCategory(
                raw_incident_type=raw_incident_type,
                category=body.category,
                subcategory=body.subcategory,
                created_at=now,
                updated_at=now,
            )
        )
    db.commit()
    return CategoryResult(
        raw_incident_type=raw_incident_type,
        category=body.category,
        subcategory=body.subcategory,
    )
