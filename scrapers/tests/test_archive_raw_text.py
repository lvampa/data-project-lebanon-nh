import gzip
import json
import socket

import pytest
from alembic import command
from alembic.config import Config
from maintenance.archive_raw_text import (
    BEFORE_DROP,
    check_raw_text_archived,
    copy_raw_text,
    main,
)
from mongo.raw_text import ENTRY_TEXT_SOURCE, PDF_TEXT_SOURCE
from postgres_testing.plugin import ALEMBIC_INI
from sqlalchemy import inspect, text

PDF_TEXT = "For Date: 05/11/2026 ...\n26-13339 0106 Phone - Noise Complaint"


@pytest.fixture
def alembic_config(db_connection):
    config = Config(ALEMBIC_INI)
    config.attributes["connection"] = db_connection
    return config


@pytest.fixture
def before_drop(alembic_config, db_connection):
    """The schema as it is before the raw text columns go, with one PDF and entry."""
    command.downgrade(alembic_config, BEFORE_DROP)
    db_connection.execute(
        text(
            "INSERT INTO pdf_urls (canonical_url, state, raw_text, created_at)"
            " VALUES ('https://example.com/a', 'complete', :text, now()),"
            "        ('https://example.com/b', 'pending', NULL, now())"
        ),
        {"text": PDF_TEXT},
    )
    db_connection.execute(
        text(
            "INSERT INTO log_entries (case_number, source_url, log_date, raw_text,"
            " raw_reason_action, scraped_at, created_at, updated_at)"
            " VALUES ('26-13339', 'https://example.com/a', '2026-05-11',"
            " '26-13339 0106 Phone - Noise Complaint',"
            " 'Noise Complaint Log Information', now(), now(), now())"
        )
    )
    return alembic_config


def columns(db_connection, table: str) -> set[str]:
    return {column["name"] for column in inspect(db_connection).get_columns(table)}


def test_copy_puts_each_value_in_the_archive(before_drop, db_session, raw_sources):
    results = copy_raw_text(db_session, raw_sources)

    assert [(r.source, r.in_postgres, r.in_archive) for r in results] == [
        (PDF_TEXT_SOURCE, 1, 1),
        (ENTRY_TEXT_SOURCE, 1, 1),
    ]
    pdf = raw_sources.find_one({"source": PDF_TEXT_SOURCE})
    assert pdf["source_key"] == "https://example.com/a"
    assert gzip.decompress(pdf["body_gzip"]).decode() == PDF_TEXT
    entry = raw_sources.find_one({"source": ENTRY_TEXT_SOURCE})
    assert entry["source_key"] == "26-13339"
    assert json.loads(gzip.decompress(entry["body_gzip"])) == {
        "raw_text": "26-13339 0106 Phone - Noise Complaint",
        "raw_reason_action": "Noise Complaint Log Information",
        "source_url": "https://example.com/a",
    }


def test_copying_twice_stores_each_value_once(before_drop, db_session, raw_sources):
    copy_raw_text(db_session, raw_sources)
    copy_raw_text(db_session, raw_sources)

    assert raw_sources.count_documents({}) == 2


def test_the_check_finds_a_value_missing_from_the_archive(
    before_drop, db_session, raw_sources
):
    copy_raw_text(db_session, raw_sources)
    raw_sources.delete_one({"source": ENTRY_TEXT_SOURCE})

    results = check_raw_text_archived(db_session, raw_sources)

    assert [r.complete for r in results] == [True, False]


def test_the_migration_refuses_to_drop_text_that_is_not_archived(
    before_drop, db_connection, raw_sources
):
    with pytest.raises(RuntimeError, match="archive_raw_text"):
        command.upgrade(before_drop, "head")

    assert "raw_text" in columns(db_connection, "log_entries")


def test_the_migration_drops_the_columns_once_the_text_is_archived(
    before_drop, db_connection, db_session, raw_sources
):
    copy_raw_text(db_session, raw_sources)

    command.upgrade(before_drop, "head")

    assert {"raw_text", "raw_reason_action", "scraped_at"}.isdisjoint(
        columns(db_connection, "log_entries")
    )
    assert "raw_text" not in columns(db_connection, "pdf_urls")


def test_with_no_text_left_the_migration_does_not_need_mongodb(
    alembic_config, db_connection, monkeypatch
):
    command.downgrade(alembic_config, BEFORE_DROP)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        monkeypatch.setenv("MONGO_PORT", str(probe.getsockname()[1]))

    command.upgrade(alembic_config, "head")

    assert "raw_text" not in columns(db_connection, "pdf_urls")


def test_main_reports_nothing_to_copy_once_the_columns_are_gone(
    db_connection, raw_sources, capsys
):
    assert main() == 0
    assert "already dropped" in capsys.readouterr().out
