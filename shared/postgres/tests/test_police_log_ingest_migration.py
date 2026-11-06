import pytest
from alembic import command
from alembic.config import Config
from postgres_testing.plugin import ALEMBIC_INI
from sqlalchemy import text

BEFORE = "ddaee8540ca5"
REVISION = "3f1a9c7e2b54"


@pytest.fixture
def alembic_config(db_connection):
    config = Config(ALEMBIC_INI)
    config.attributes["connection"] = db_connection
    command.downgrade(config, BEFORE)
    return config


def add_entry(connection, case_number, source_url, reported_at) -> None:
    connection.execute(
        text(
            "INSERT INTO log_entries"
            " (case_number, source_url, reported_at, raw_text, scraped_at)"
            " VALUES (:case_number, :source_url, :reported_at, 'text',"
            " '2026-06-07 17:48:00')"
        ),
        {
            "case_number": case_number,
            "source_url": source_url,
            "reported_at": reported_at,
        },
    )


def add_url(connection, canonical_url, **columns) -> None:
    values = {"canonical_url": canonical_url, "created_at": "2026-06-01", **columns}
    names = ", ".join(values)
    placeholders = ", ".join(f":{name}" for name in values)
    connection.execute(
        text(f"INSERT INTO pdf_urls ({names}) VALUES ({placeholders})"), values
    )


def entry(connection, case_number):
    return connection.execute(
        text("SELECT * FROM log_entries WHERE case_number = :case_number"),
        {"case_number": case_number},
    ).one()


def url(connection, canonical_url):
    return connection.execute(
        text("SELECT * FROM pdf_urls WHERE canonical_url = :canonical_url"),
        {"canonical_url": canonical_url},
    ).one()


def test_log_date_comes_from_the_url_record(db_connection, alembic_config):
    # Reported just after midnight, so the report date is not the log date.
    add_url(db_connection, "https://example.com/2026-05-11", log_date="2026-05-11")
    add_entry(
        db_connection, "26-1", "https://example.com/2026-05-11", "2026-05-12 00:04"
    )

    command.upgrade(alembic_config, REVISION)

    assert str(entry(db_connection, "26-1").log_date) == "2026-05-11"


def test_log_date_falls_back_to_the_reported_date(db_connection, alembic_config):
    add_entry(db_connection, "26-2", "https://example.com/gone", "2026-05-13 09:30")

    command.upgrade(alembic_config, REVISION)

    assert str(entry(db_connection, "26-2").log_date) == "2026-05-13"


def test_upgrade_fails_when_an_entry_has_no_log_date(db_connection, alembic_config):
    add_entry(db_connection, "26-3", "https://example.com/gone", None)

    with pytest.raises(RuntimeError, match="1 log entries have no log date"):
        command.upgrade(alembic_config, REVISION)


def test_created_and_updated_start_at_scraped_at(db_connection, alembic_config):
    add_entry(db_connection, "26-4", "https://example.com/gone", "2026-05-13 09:30")

    command.upgrade(alembic_config, REVISION)

    row = entry(db_connection, "26-4")
    assert row.created_at == row.scraped_at
    assert row.updated_at == row.scraped_at


def test_entry_count_becomes_parsed_and_stored_counts(db_connection, alembic_config):
    add_url(db_connection, "https://example.com/a", state="complete", entry_count=110)

    command.upgrade(alembic_config, REVISION)

    row = url(db_connection, "https://example.com/a")
    assert (row.parsed_count, row.stored_count) == (110, 110)


@pytest.mark.parametrize(
    ("raw_text", "error_kind"), [(None, "download"), ("pdf text", "parse")]
)
def test_existing_errors_get_a_kind(
    db_connection, alembic_config, raw_text, error_kind
):
    add_url(db_connection, "https://example.com/a", state="error", raw_text=raw_text)

    command.upgrade(alembic_config, REVISION)

    assert url(db_connection, "https://example.com/a").error_kind == error_kind
