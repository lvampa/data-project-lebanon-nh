import gzip
import json
import socket

import pytest
from alembic import command
from alembic.config import Config
from maintenance import archive_raw_text
from maintenance.archive_raw_text import BEFORE_DROP, copy_raw_text, main
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
    """The schema before the raw text columns go, with PDFs and entries in it.

    One entry predates the parser's version, as the 343 live rows do.
    """
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
            " raw_reason_action, parser_version, scraped_at, created_at, updated_at)"
            " VALUES ('26-13339', 'https://example.com/a', '2026-05-11',"
            " '26-13339 0106 Phone - Noise Complaint',"
            " 'Noise Complaint Log Information', NULL, now(), now(), now()),"
            " ('26-13340', 'https://example.com/a', '2026-05-11',"
            " '26-13340 0200 Phone - Alarm', 'Alarm', 1, now(), now(), now())"
        )
    )
    return alembic_config


@pytest.fixture
def legacy_urls(raw_sources):
    """The old Mongo urls collection: one text of its own, one the same as pdf_urls."""
    urls = raw_sources.database["urls"]
    urls.drop()
    urls.insert_many(
        [
            {"canonical_url": "https://example.com/old", "raw_text": "old log text"},
            {"canonical_url": "https://example.com/a", "raw_text": PDF_TEXT},
            {"canonical_url": "https://example.com/never-read", "state": "pending"},
        ]
    )
    try:
        yield urls
    finally:
        urls.drop()


def columns(db_connection, table: str) -> set[str]:
    return {column["name"] for column in inspect(db_connection).get_columns(table)}


def stored(raw_sources, source: str) -> dict[str, dict]:
    return {doc["source_key"]: doc for doc in raw_sources.find({"source": source})}


def test_copy_puts_each_value_in_the_archive(
    before_drop, db_session, raw_sources, legacy_urls
):
    results = copy_raw_text(db_session, raw_sources)

    assert [(r.origin, r.found, r.archived) for r in results] == [
        ("pdf_urls.raw_text", 1, 1),
        ("urls.raw_text", 2, 2),
        ("log_entries.raw_text", 2, 2),
    ]
    pdfs = stored(raw_sources, PDF_TEXT_SOURCE)
    assert set(pdfs) == {"https://example.com/a", "https://example.com/old"}
    assert (
        gzip.decompress(pdfs["https://example.com/a"]["body_gzip"]).decode() == PDF_TEXT
    )
    entry = stored(raw_sources, ENTRY_TEXT_SOURCE)["26-13339"]
    assert json.loads(gzip.decompress(entry["body_gzip"])) == {
        "raw_text": "26-13339 0106 Phone - Noise Complaint",
        "raw_reason_action": "Noise Complaint Log Information",
        "source_url": "https://example.com/a",
        "parser_version": None,
    }
    later = stored(raw_sources, ENTRY_TEXT_SOURCE)["26-13340"]
    assert json.loads(gzip.decompress(later["body_gzip"]))["parser_version"] == 1


def test_the_urls_collection_is_left_unchanged(
    before_drop, db_session, raw_sources, legacy_urls
):
    before = list(legacy_urls.find())

    copy_raw_text(db_session, raw_sources)

    assert list(legacy_urls.find()) == before


def test_a_second_run_changes_nothing(
    before_drop, db_session, raw_sources, legacy_urls
):
    copy_raw_text(db_session, raw_sources)
    first = list(raw_sources.find().sort("_id", 1))

    results = copy_raw_text(db_session, raw_sources)

    assert list(raw_sources.find().sort("_id", 1)) == first
    assert all(result.complete for result in results)


def test_a_value_that_did_not_arrive_fails_the_run(
    before_drop, db_session, raw_sources, legacy_urls, monkeypatch, capsys
):
    real_write = archive_raw_text._write
    writes = iter([real_write, real_write, lambda collection, versions: None])
    monkeypatch.setattr(archive_raw_text, "_write", lambda c, v: next(writes)(c, v))

    assert main() == 1

    out = capsys.readouterr()
    assert "log_entries.raw_text: 2 found, 0 archived" in out.out
    assert "Do not drop the columns" in out.err


def test_a_complete_copy_says_the_migration_can_run(
    before_drop, raw_sources, legacy_urls, capsys
):
    assert main() == 0
    assert "The migration can drop the columns now." in capsys.readouterr().out


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
