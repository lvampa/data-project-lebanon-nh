"""Pytest plugin that runs database tests against a Postgres database named `*_test`.

It loads through the `pytest11` entry point, so every suite in the workspace gets it
without a conftest.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from postgres import client, get_engine, get_postgres_settings, open_session
from sqlalchemy import URL, Connection, Engine, create_engine, text
from sqlalchemy.exc import OperationalError, UnboundExecutionError
from sqlalchemy.orm import Session

TEST_DATABASE = os.environ.get("TEST_POSTGRES_DB", "app_test")

# Only for the local compose database. Tests never read .env.
TEST_PASSWORD = "app"

# The workspace is installed from its source tree, so alembic.ini sits beside src/.
POSTGRES_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = POSTGRES_PACKAGE_ROOT / "alembic.ini"


def is_test_database(name: str | None) -> bool:
    return bool(name) and name.endswith("_test")


def pytest_configure(config: pytest.Config) -> None:
    if not is_test_database(TEST_DATABASE):
        pytest.exit(
            f"Refusing to run tests: Postgres database {TEST_DATABASE!r} "
            "does not end in '_test'.",
            returncode=pytest.ExitCode.USAGE_ERROR,
        )
    # Settings and the engine are read on first use, which is after this point.
    # The cache clears cover a conftest or plugin that asked for them while importing.
    os.environ["POSTGRES_DB"] = TEST_DATABASE
    os.environ.setdefault("POSTGRES_PASSWORD", TEST_PASSWORD)
    get_postgres_settings.cache_clear()
    get_engine.cache_clear()


@pytest.fixture(autouse=True)
def _sessions_unbound_outside_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give sessions no database until a test asks for `db_connection`.

    A test that forgets the fixture then fails with SQLAlchemy's unbound error,
    where it would otherwise commit rows to the test database for good.
    """

    def no_database() -> Session:
        raise UnboundExecutionError("This test needs the `db_connection` fixture.")

    monkeypatch.setattr(client, "_new_session", no_database)


@pytest.fixture(scope="session")
def test_engine() -> Engine:
    """The engine for the migrated test database."""
    engine = get_engine()
    if not is_test_database(engine.url.database):
        pytest.exit(
            f"Refusing to run tests: the Postgres engine points at "
            f"{engine.url.database!r}, which does not end in '_test'.",
            returncode=pytest.ExitCode.USAGE_ERROR,
        )
    # Only the first connection is guarded: an error from a migration is a real
    # failure and should not be reported as "Postgres is not running".
    try:
        _create_database_if_missing(engine.url)
    except OperationalError:
        unreachable = True
    else:
        unreachable = False
    # Failing outside the except block keeps the driver's traceback out of the report.
    if unreachable:
        pytest.fail(
            f"Database tests need Postgres at {engine.url.host}:{engine.url.port}. "
            "Start it with `docker compose up -d postgres`.",
            pytrace=False,
        )
    _upgrade_to_head(engine)
    return engine


@pytest.fixture
def db_connection(
    test_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Connection]:
    """One connection inside a transaction that is rolled back after the test.

    Sessions are opened on it, so a commit in the code under test only releases
    a savepoint and nothing reaches the database.
    """
    with test_engine.connect() as connection:
        transaction = connection.begin()
        monkeypatch.setattr(
            client,
            "_new_session",
            lambda: Session(bind=connection, join_transaction_mode="create_savepoint"),
        )
        try:
            yield connection
        finally:
            transaction.rollback()


@pytest.fixture
def db_session(db_connection: Connection) -> Iterator[Session]:
    """A session for arranging and asserting, on the test's rolled-back connection."""
    with open_session() as session:
        yield session


def _create_database_if_missing(url: URL) -> None:
    maintenance = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        with maintenance.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            )
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        maintenance.dispose()


def _upgrade_to_head(engine: Engine) -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(ALEMBIC_INI)
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        connection.commit()
