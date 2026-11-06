"""Run the process_urls spider and report failure through the exit code.

`scrapy crawl` exits 0 even when PDFs fail, so the scheduler would never see it.

    uv run python run_process_urls.py --limit 100

Set LOGFIRE_SEND_TO_LOGFIRE=false to run by hand without sending traces.
"""

import argparse
import sys
from datetime import datetime
from typing import Any

import logfire
from ingest.lock import police_log_lock
from ingest.pdf_urls import utc_now
from postgres import SessionLocal, engine
from postgres.models.pdf_url import PdfUrl
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def crawl(limit: int) -> dict[str, Any]:
    """Run the spider to the end and return its stats."""
    process = CrawlerProcess(get_project_settings())
    crawler = process.create_crawler("process_urls")
    process.crawl(crawler, limit=limit)
    process.start()
    return crawler.stats.get_stats()


def crawl_failed(stats: dict[str, Any]) -> bool:
    """Whether the crawl broke, as opposed to single PDFs failing.

    A spider that cannot claim URLs, say because the database is down, changes no
    URL record, so counting records in error would miss it.
    """
    return stats.get("finish_reason") != "finished" or bool(
        stats.get("log_count/ERROR")
    )


def count_errors_since(session: Session, started_at: datetime) -> int:
    return session.scalar(
        select(func.count())
        .select_from(PdfUrl)
        .where(PdfUrl.state == "error", PdfUrl.completed_at >= started_at)
    )


def main(limit: int) -> int:
    with police_log_lock(engine) as acquired:
        if not acquired:
            print(
                "Another police log job (process or reprocess) is running. "
                "Wait for it to finish, then run this again.",
                file=sys.stderr,
            )
            return 1

        started_at = utc_now()
        stats = crawl(limit)
        with SessionLocal() as session:
            errors = count_errors_since(session, started_at)

    if crawl_failed(stats):
        print(
            "The crawl did not finish cleanly; see the errors logged above.",
            file=sys.stderr,
        )
        return 1
    if errors:
        logfire.error("police log urls moved to error", count=errors)
        print(f"{errors} PDF URL(s) moved to error during this run.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10, help="Max URLs to process")
    sys.exit(main(parser.parse_args().limit))
