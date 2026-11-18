from functools import cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from .settings import get_postgres_settings


# Built on first use, not on import, so an entry point can load .env first.
# Scrapers and DAGs run for hours, so a connection can be dropped by the server
# while the pool holds it. pre_ping replaces a dead connection instead of raising.
@cache
def get_engine() -> Engine:
    return create_engine(get_postgres_settings().url, pool_pre_ping=True)


def _new_session() -> Session:
    # The test plugin replaces this to put sessions on its rolled-back connection.
    return Session(bind=get_engine())


def open_session() -> Session:
    """A new session on the shared engine. The caller closes it."""
    return _new_session()
