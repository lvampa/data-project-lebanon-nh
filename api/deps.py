from collections.abc import Generator
from dataclasses import dataclass

from elasticsearch import Elasticsearch
from fastapi import Query, Request
from postgres import SessionLocal
from sqlalchemy import Select
from sqlalchemy.orm import Session


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_es(request: Request) -> Elasticsearch:
    return request.app.state.es


@dataclass(frozen=True)
class Paging:
    page: int
    per_page: int

    def apply(self, stmt: Select) -> Select:
        return stmt.offset((self.page - 1) * self.per_page).limit(self.per_page)


def get_paging(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
) -> Paging:
    return Paging(page=page, per_page=per_page)
