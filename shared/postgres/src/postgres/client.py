import os

from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def _build_url() -> URL:
    return URL.create(
        "postgresql+psycopg2",
        username=os.environ.get("POSTGRES_USER", "app"),
        password=os.environ.get("POSTGRES_PASSWORD", "app"),
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DB", "app"),
    )


# Scrapers and DAGs run for hours, so a connection can be dropped by the server
# while the pool holds it. pre_ping replaces a dead connection instead of raising.
engine: Engine = create_engine(_build_url(), pool_pre_ping=True)

SessionLocal: sessionmaker[Session] = sessionmaker(bind=engine)
