import pytest
from alembic import command
from alembic.config import Config
from postgres_testing.plugin import ALEMBIC_INI
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def alembic_config(db_connection):
    # Alembic joins the test's connection, so every step is rolled back with it.
    config = Config(ALEMBIC_INI)
    config.attributes["connection"] = db_connection
    return config


def test_migrations_run_up_and_down_and_match_models(alembic_config):
    command.downgrade(alembic_config, "base")

    command.upgrade(alembic_config, "head")
    command.check(alembic_config)
    command.downgrade(alembic_config, "base")


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
def test_constraints_reject_invalid_rows(db_connection, statement):
    with pytest.raises(IntegrityError):
        db_connection.execute(text(statement))
