import os
import subprocess
import sys
from collections.abc import Iterator

import pytest
from mongo.client import MongoDB
from postgres.client import engine
from sqlalchemy import create_engine, text

from scripts import migrate

THROWAWAY_POSTGRES = "app_migrate_cmd_test"
THROWAWAY_MONGO = "scraped_data_migrate_cmd_test"


def run_migrate(**environment: str) -> subprocess.CompletedProcess[str]:
    # A subprocess, because postgres.client builds its engine from POSTGRES_* when it
    # is first imported, and this suite has already pointed it at app_test.
    env = {**os.environ, **environment}
    return subprocess.run(
        [sys.executable, "-m", "scripts.migrate"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def throwaway_databases() -> Iterator[dict[str, str]]:
    """An empty Postgres database and an empty MongoDB database, dropped afterwards."""
    server = create_engine(
        engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    mongo = MongoDB()
    with server.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{THROWAWAY_POSTGRES}"'))
        connection.execute(text(f'CREATE DATABASE "{THROWAWAY_POSTGRES}"'))
    try:
        yield {"POSTGRES_DB": THROWAWAY_POSTGRES, "MONGO_DB": THROWAWAY_MONGO}
    finally:
        with server.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{THROWAWAY_POSTGRES}"'))
        mongo.get_collection("any", db=THROWAWAY_MONGO).database.client.drop_database(
            THROWAWAY_MONGO
        )
        server.dispose()


def migrated_revision() -> str:
    database = create_engine(engine.url.set(database=THROWAWAY_POSTGRES))
    try:
        with database.connect() as connection:
            return connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
    finally:
        database.dispose()


def consumer_views() -> set[str]:
    database = create_engine(engine.url.set(database=THROWAWAY_POSTGRES))
    try:
        with database.connect() as connection:
            return set(
                connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.views"
                        " WHERE table_schema = 'marts'"
                    )
                ).scalars()
            )
    finally:
        database.dispose()


def mongo_index_names() -> set[str]:
    collection = MongoDB().get_collection("urls", db=THROWAWAY_MONGO)
    return set(collection.index_information())


def test_a_fresh_migrate_applies_both_steps_and_a_rerun_changes_nothing(
    throwaway_databases,
):
    first = run_migrate(**throwaway_databases)
    revision, indexes = migrated_revision(), mongo_index_names()
    views = consumer_views()
    second = run_migrate(**throwaway_databases)

    assert first.returncode == 0, first.stdout + first.stderr
    assert "Running upgrade" in first.stderr
    assert "canonical_url_1" in indexes
    assert {"incidents", "public_incidents", "public_properties"} <= views
    # The rerun drops the views first and builds them again.
    assert second.returncode == 0, second.stdout + second.stderr
    assert "Running upgrade" not in second.stderr
    assert migrated_revision() == revision
    assert mongo_index_names() == indexes
    assert consumer_views() == views


def test_it_stops_at_the_first_failure_with_a_clear_message(throwaway_databases):
    result = run_migrate(**{**throwaway_databases, "POSTGRES_PORT": "1"})

    assert result.returncode == 1
    # Postgres is unreachable, so the first step, the drop, is the one that fails.
    assert "Dropping the consumer models failed" in result.stderr
    assert "Mongo indexes initialized" not in result.stdout


def test_the_steps_run_in_order_and_stop_at_the_first_failure(monkeypatch, capsys):
    calls: list[str] = []

    def failing() -> None:
        calls.append("postgres")
        raise RuntimeError("no database")

    monkeypatch.setattr(
        migrate,
        "STEPS",
        [("Postgres", failing), ("Mongo", lambda: calls.append("mongo"))],
    )
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)

    assert migrate.main() == 1
    assert calls == ["postgres"]
    assert capsys.readouterr().err == "Postgres failed: no database\n"


def test_the_views_are_dropped_first_and_built_last():
    names = [name for name, _ in migrate.STEPS]

    assert names[0] == "Dropping the consumer models"
    assert names[-1] == "Consumer models (dbt build)"
    assert names[1:3] == ["Postgres migrations", "MongoDB indexes"]


def test_a_failed_dbt_build_says_the_migrations_applied(monkeypatch):
    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        failed = command[1] == "build"
        return subprocess.CompletedProcess(command, 1 if failed else 0)

    monkeypatch.setattr(migrate.subprocess, "run", fake_run)

    with pytest.raises(
        RuntimeError, match="migrations applied; consumer models failed"
    ):
        migrate.build_consumer_models()
