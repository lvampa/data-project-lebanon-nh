from logging.config import fileConfig

import postgres.models  # noqa: F401 — registers models with Base.metadata
from alembic import context
from postgres.base import Base
from postgres.client import engine
from sqlalchemy import Connection

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=engine.url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Tests pass their own connection so the migrations join its transaction.
    connection = config.attributes.get("connection")
    if connection is None:
        with engine.connect() as connection:
            _run_migrations(connection)
    else:
        _run_migrations(connection)


def _run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
