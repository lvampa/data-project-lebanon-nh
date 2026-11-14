from datetime import UTC, datetime
from typing import Any, cast

import logfire
from postgres.models.incident_type_category import IncidentTypeCategory
from postgres.models.log_entry import LogEntry
from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from api.deps import NormalizationFilter, Paging
from api.schemas import CategoryRecord, CategoryResult, CategoryUpdate, Page
from api.services.normalizations import apply_filter


def list_categories(
    db: Session, paging: Paging, filters: NormalizationFilter
) -> Page[CategoryRecord]:
    columns = (
        IncidentTypeCategory.category,
        IncidentTypeCategory.normalized_type,
        IncidentTypeCategory.source,
        IncidentTypeCategory.needs_review,
    )
    stmt = (
        select(LogEntry.incident_type, func.count().label("count"), *columns)
        .outerjoin(
            IncidentTypeCategory,
            LogEntry.incident_type == IncidentTypeCategory.raw_incident_type,
        )
        .where(LogEntry.incident_type.isnot(None))
        .group_by(LogEntry.incident_type, *columns)
    )
    stmt = apply_filter(
        stmt,
        IncidentTypeCategory.source,
        IncidentTypeCategory.needs_review,
        IncidentTypeCategory.category,
        filters,
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
                normalized_type=r.normalized_type,
                subcategory=r.normalized_type,
                source=r.source,
                needs_review=bool(r.needs_review),
                is_categorized=r.category is not None,
            )
            for r in rows
        ],
    )


def update_category(
    db: Session, raw_incident_type: str, update: CategoryUpdate
) -> CategoryResult:
    now = datetime.now(UTC).replace(tzinfo=None)
    # A human value has no prompt version. The AI call that came before it stays in
    # ai_call_id, so the AI's answer can be compared with this correction.
    changes = {
        "category": update.category,
        "normalized_type": update.normalized_type,
        "source": "human",
        "needs_review": False,
        "prompt_version": None,
        "updated_at": now,
    }
    with logfire.span(
        "upsert incident type category {raw_incident_type}",
        raw_incident_type=raw_incident_type,
    ):
        db.execute(
            insert(IncidentTypeCategory)
            .values(raw_incident_type=raw_incident_type, created_at=now, **changes)
            .on_conflict_do_update(index_elements=["raw_incident_type"], set_=changes)
        )
        db.commit()
    return CategoryResult(
        raw_incident_type=raw_incident_type,
        category=update.category,
        normalized_type=update.normalized_type,
    )


def delete_category(db: Session, raw_incident_type: str) -> bool:
    """Hand a value back to AI: its row and its failed attempts go. False if no row."""
    with logfire.span(
        "delete incident type category {raw_incident_type}",
        raw_incident_type=raw_incident_type,
    ):
        result = db.execute(
            delete(IncidentTypeCategory).where(
                IncidentTypeCategory.raw_incident_type == raw_incident_type
            )
        )
        db.commit()
    return cast(CursorResult[Any], result).rowcount > 0
