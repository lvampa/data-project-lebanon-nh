import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is not set; these tests need an empty Postgres database",
)


@pytest.fixture
def migrated():
    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:
        # Alembic joins this outer transaction, so rolling it back leaves the
        # test database empty even when a step fails.
        transaction = connection.begin()
        config = Config(ALEMBIC_INI)
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        yield connection, config
        transaction.rollback()
    engine.dispose()


def test_migrations_match_models_and_downgrade_cleanly(migrated):
    _, config = migrated

    command.check(config)
    command.downgrade(config, "base")


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO llcs (name, lookup_status, created_at)"
        " VALUES ('X LLC', 'bogus', now())",
        "INSERT INTO budget_documents (fiscal_year, document_type, source_url, scraped_at)"
        " VALUES (2026, 'bogus', 'https://example.com', now())",
        "INSERT INTO address_normalizations (raw_address, geocoded_via, created_at, updated_at)"
        " VALUES ('1 MAIN ST', 'bogus', now(), now())",
        "INSERT INTO planning_documents (civicclerk_file_id, civicclerk_event_id, scraped_at)"
        " VALUES (1, 999, now())",
        "INSERT INTO pdf_urls (canonical_url, state, created_at)"
        " VALUES ('https://example.com/a.pdf', 'bogus', now())",
    ],
    ids=[
        "lookup_status",
        "document_type",
        "geocoded_via",
        "planning_event_fk",
        "pdf_url_state",
    ],
)
def test_constraints_reject_invalid_rows(migrated, statement):
    connection, _ = migrated

    with pytest.raises(IntegrityError):
        connection.execute(text(statement))
