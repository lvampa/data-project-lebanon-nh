import os
from functools import lru_cache
from typing import Any, override

from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.session import _EntityBindKey


def _build_url() -> URL:
    return URL.create(
        "postgresql+psycopg2",
        username=os.environ.get("POSTGRES_USER", "app"),
        password=os.environ.get("POSTGRES_PASSWORD", "app"),
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DB", "app"),
    )


# Built on first use, not on import, so an entry point can load .env first.
# Scrapers and DAGs run for hours, so a connection can be dropped by the server
# while the pool holds it. pre_ping replaces a dead connection instead of raising.
@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(_build_url(), pool_pre_ping=True)


class _Session(Session):
    """Falls back to the shared engine when nothing is bound.

    The test plugin passes `default_engine=False` so a test that forgets its
    fixture fails instead of writing to the test database.
    """

    def __init__(self, *args: Any, default_engine: bool = True, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._default_engine = default_engine

    @override
    def get_bind(
        self, mapper: _EntityBindKey[Any] | None = None, **kwargs: Any
    ) -> Engine | Connection:
        if self.bind is None and self._default_engine:
            return get_engine()
        return super().get_bind(mapper, **kwargs)


SessionLocal: sessionmaker[Session] = sessionmaker(class_=_Session)
