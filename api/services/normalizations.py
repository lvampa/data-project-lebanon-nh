"""What the two admin lists share: their filters."""

from typing import Any

from sqlalchemy import Select, or_
from sqlalchemy.orm import InstrumentedAttribute

from api.deps import NormalizationFilter


def apply_filter[SelectT: Select[*tuple[Any, ...]]](
    stmt: SelectT,
    source: InstrumentedAttribute[Any],
    needs_review: InstrumentedAttribute[Any],
    value: InstrumentedAttribute[Any],
    filters: NormalizationFilter,
) -> SelectT:
    """Narrow an outer-joined list by who set the value, the review mark, and whether
    a normalized value exists yet. `value` is the column that is empty while it waits."""
    if filters.source is not None:
        stmt = stmt.where(source == filters.source)
    if filters.needs_review is True:
        stmt = stmt.where(needs_review.is_(True))
    elif filters.needs_review is False:
        # A raw value with no row has no review mark, which counts as unmarked.
        stmt = stmt.where(or_(needs_review.is_(False), needs_review.is_(None)))
    if filters.normalized is True:
        stmt = stmt.where(value.is_not(None))
    elif filters.normalized is False:
        stmt = stmt.where(value.is_(None))
    return stmt
