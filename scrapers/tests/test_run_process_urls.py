import logging
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import run_process_urls
from ingest.lock import police_log_lock
from ingest.pdf_urls import utc_now
from mongo.archive import ArchivedResponse, RawArchive, archive_collection
from mongo.client import MongoDB
from postgres.models.pdf_url import PdfUrl

ARCHIVED_PDF = ArchivedResponse(
    url="https://example.com/a",
    status=200,
    content_type="application/pdf",
    body=b"%PDF-1.4",
    fetched_at=datetime(2026, 11, 6, tzinfo=UTC),
    spider="process_urls",
)


def add_url(session, canonical_url: str, **columns) -> None:
    session.add(
        PdfUrl(canonical_url=canonical_url, created_at=datetime(2026, 5, 1), **columns)
    )
    session.commit()


@pytest.fixture
def crawl(monkeypatch):
    """Stand in for the crawl. Tests set `crawl.during` to what a run would do."""

    def fake_crawl(limit: int) -> dict:
        fake_crawl.limits.append(limit)
        fake_crawl.during()
        return fake_crawl.stats

    fake_crawl.limits = []
    fake_crawl.during = lambda: None
    fake_crawl.stats = {"finish_reason": "finished"}
    monkeypatch.setattr(run_process_urls, "crawl", fake_crawl)
    return fake_crawl


def test_exits_zero_when_no_url_moved_to_error(db_session, crawl):
    add_url(
        db_session,
        "https://example.com/old-error.pdf",
        state="error",
        error_kind="parse",
        completed_at=utc_now() - timedelta(days=1),
    )

    assert run_process_urls.main(limit=25) == 0
    assert crawl.limits == [25]


def test_exits_non_zero_when_a_url_moved_to_error_during_the_run(
    db_session, crawl, capsys
):
    crawl.during = lambda: add_url(
        db_session,
        "https://example.com/failed.pdf",
        state="error",
        error_kind="download",
        completed_at=utc_now(),
    )

    assert run_process_urls.main(limit=25) == 1
    assert "1 PDF URL(s) moved to error" in capsys.readouterr().err


def test_does_not_crawl_while_another_police_log_job_holds_the_lock(
    test_engine, crawl, capsys
):
    with police_log_lock(test_engine) as acquired:
        assert acquired

        assert run_process_urls.main(limit=25) == 1

    assert crawl.limits == []
    assert "Another police log job" in capsys.readouterr().err


def test_lock_is_free_again_after_the_job_ends(test_engine):
    with (
        police_log_lock(test_engine) as first,
        police_log_lock(test_engine) as second,
    ):
        assert (first, second) == (True, False)

    with police_log_lock(test_engine) as third:
        assert third is True


@pytest.mark.parametrize(
    "stats",
    [
        {"finish_reason": "finished", "log_count/ERROR": 1},
        {"finish_reason": "shutdown"},
        {},
    ],
    ids=["logged_an_error", "interrupted", "never_finished"],
)
def test_exits_non_zero_when_the_crawl_itself_failed(db_session, crawl, capsys, stats):
    crawl.stats = stats

    assert run_process_urls.main(limit=25) == 1
    assert "did not finish cleanly" in capsys.readouterr().err


SPIDER_THAT_CANNOT_CLAIM = """
import sys
import run_process_urls
from spiders.process_url_records import ProcessUrlsSpider

def claim_fails(self):
    raise RuntimeError("database is down")

ProcessUrlsSpider._claim_urls = claim_fails
sys.exit(run_process_urls.main(limit=1))
"""


def test_real_crawl_that_cannot_claim_urls_exits_non_zero(test_engine):
    # A real Scrapy run, in its own process because the reactor starts only once.
    scrapers_dir = Path(run_process_urls.__file__).parent
    result = subprocess.run(
        [sys.executable, "-c", SPIDER_THAT_CANNOT_CLAIM],
        cwd=scrapers_dir,
        env={
            **os.environ,
            "POSTGRES_DB": test_engine.url.database,
            "LOGFIRE_SEND_TO_LOGFIRE": "false",
        },
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 1
    assert "database is down" in result.stderr
    assert "did not finish cleanly" in result.stderr


def test_the_archive_going_down_is_not_a_crawl_error(caplog, monkeypatch):
    # The runner fails a crawl that logged any ERROR record, and an unreachable
    # archive must not change the exit code.
    monkeypatch.setenv("MONGO_HOST", "127.0.0.1")
    monkeypatch.setenv("MONGO_PORT", "1")
    archive = RawArchive(archive_collection(MongoDB()))
    archive.add("police_log_pdf", "https://example.com/a", ARCHIVED_PDF)

    with caplog.at_level(logging.ERROR):
        archive.flush()

    assert archive.is_down is True
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []
