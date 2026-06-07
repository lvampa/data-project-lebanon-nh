import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def _build_url() -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "app")
    password = os.environ.get("POSTGRES_PASSWORD", "app")
    db = os.environ.get("POSTGRES_DB", "app")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


engine: Engine = create_engine(_build_url())

SessionLocal: sessionmaker[Session] = sessionmaker(bind=engine)
