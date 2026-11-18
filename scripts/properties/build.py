"""Build the property tables from the raw archive, by hand or from Airflow.

    uv run build-properties

It takes the newest archived page of each parcel seen in the latest finished crawl,
parses it, runs the quality checks, and replaces `properties` and `property_sales` in
one transaction. When a check fails it writes nothing, logs why, and exits 1. Run it
again after any parser fix: it reads the archive, so nothing is fetched.
"""

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import logfire
from bootstrap import bootstrap
from mongo.archive import RawArchive, archive_collection, stored_body
from mongo.client import get_db
from postgres import open_session
from postgres.models.crawl_run import CrawlRun
from postgres.models.property import Property
from postgres.models.property_sale import PropertySale
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from scripts.models.property import PropertyRecord
from scripts.properties.checks import CheckResult, run_checks
from scripts.properties.parse import parse_parcel

PARCEL_SOURCE = "vgsi_parcel"
CRAWL_SOURCE = "vgsi_property"


@dataclass(frozen=True)
class ParsedPage:
    record: PropertyRecord
    # When the archive last saw the page, as naive UTC.
    fetched_at: datetime


def latest_finished_run(session: Session) -> CrawlRun | None:
    return session.scalars(
        select(CrawlRun)
        .where(CrawlRun.source == CRAWL_SOURCE, CrawlRun.finished_at.is_not(None))
        .order_by(CrawlRun.started_at.desc())
        .limit(1)
    ).first()


def parse_archive(archive: RawArchive, run: CrawlRun) -> tuple[list[ParsedPage], int]:
    """The newest page of each parcel the run saw, parsed, and how many would not parse."""
    pages: list[ParsedPage] = []
    unparsed = 0
    for key in archive.keys(PARCEL_SOURCE):
        version = archive.newest(PARCEL_SOURCE, key)
        body = stored_body(version) if version is not None else None
        if version is None or body is None:
            continue
        fetched_at = _naive_utc(
            version.get("last_seen_at") or version["first_fetched_at"]
        )
        # A parcel the run did not see has gone from the town's list.
        if fetched_at < run.started_at:
            continue
        try:
            pages.append(ParsedPage(parse_parcel(body, version["url"]), fetched_at))
        except Exception as exc:
            unparsed += 1
            logfire.warning("parcel page did not parse", pid=key, error=repr(exc))
    return pages, unparsed


def replace_properties(
    session: Session, run: CrawlRun, pages: Sequence[ParsedPage]
) -> int:
    """Empty both tables and fill them from the pages. Returns the sales written."""
    session.execute(delete(PropertySale))
    session.execute(delete(Property))
    sales: list[dict[str, Any]] = []
    for page in pages:
        lineage = {"crawl_run_id": run.id, "fetched_at": page.fetched_at}
        property_id = session.execute(
            insert(Property)
            .values(**page.record.model_dump(exclude={"sales"}), **lineage)
            .returning(Property.id)
        ).scalar_one()
        sales += [
            {"property_id": property_id, **sale.model_dump(), **lineage}
            for sale in page.record.sales
        ]
    if sales:
        session.execute(insert(PropertySale), sales)
    return len(sales)


def main(argv: Sequence[str] | None = None) -> int:
    bootstrap("build-properties")
    with open_session() as session:
        run = latest_finished_run(session)
        if run is None:
            logfire.error("no finished crawl of vgsi_property; run the crawl first")
            return 1

        run_id = run.id
        archive = RawArchive(archive_collection(get_db()))
        pages, unparsed = parse_archive(archive, run)
        current = session.scalar(select(func.count()).select_from(Property)) or 0
        results = run_checks([page.record for page in pages], current)
        print("\n".join(_check_lines(results)))
        failed = [result for result in results if not result.passed]
        for result in failed:
            logfire.error(
                "property build check failed: {check}: {detail}",
                check=result.name,
                detail=result.detail,
            )
        if failed:
            print(f"Nothing written. The tables still hold {current} parcels.")
            return 1

        # The key is not empty on the parcels that pass; the rest cannot be stored.
        keyed = [page for page in pages if page.record.mblu]
        sales = replace_properties(session, run, keyed)
        session.commit()
    print(
        f"Built {len(keyed)} parcels and {sales} sales from crawl run {run_id}. "
        f"{unparsed} pages did not parse, and {len(pages) - len(keyed)} had no mblu."
    )
    return 0


def _check_lines(results: Sequence[CheckResult]) -> list[str]:
    return [
        f"{'ok  ' if result.passed else 'FAIL'} {result.name}: {result.detail}"
        for result in results
    ]


def _naive_utc(moment: datetime) -> datetime:
    if moment.tzinfo is not None:
        return moment.astimezone(UTC).replace(tzinfo=None)
    return moment


if __name__ == "__main__":
    sys.exit(main())
