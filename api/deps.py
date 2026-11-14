from collections.abc import Generator
from dataclasses import dataclass

from fastapi import Query
from postgres import SessionLocal
from sqlalchemy import Select
from sqlalchemy.orm import Session

from api.schemas import Source


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@dataclass(frozen=True)
class Paging:
    page: int
    per_page: int

    def apply(self, stmt: Select) -> Select:
        return stmt.offset((self.page - 1) * self.per_page).limit(self.per_page)


@dataclass(frozen=True)
class NormalizationFilter:
    """The filters of the admin lists: who set the value, review mark, and existence."""

    source: Source | None
    needs_review: bool | None
    normalized: bool | None


def get_normalization_filter(
    source: Source | None = None,
    needs_review: bool | None = None,
    normalized: bool | None = None,
) -> NormalizationFilter:
    return NormalizationFilter(source, needs_review, normalized)


def get_paging(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
) -> Paging:
    return Paging(page=page, per_page=per_page)
