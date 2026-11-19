"""Rebuild `properties` and `property_sales` from the raw archive.

It takes the newest archived page of each parcel seen in the latest finished
`vgsi_property` crawl, parses it, runs the quality checks, and replaces both tables in
one transaction. When a check fails it writes nothing.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import logfire
from models.property import PropertyRecord
from mongo.archive import RawArchive, stored_body
from parsers.vgsi_parcel import parse_parcel
from postgres import to_naive_utc
from postgres.models.crawl_run import CrawlRun
from postgres.models.property import Property
from postgres.models.property_sale import PropertySale
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from ingest.property_checks import CheckResult, run_checks

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
        fetched_at = to_naive_utc(
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


@dataclass(frozen=True)
class BuildResult:
    checks: list[CheckResult] = field(default_factory=list)
    # Parcels in the table before the build.
    current: int = 0
    # None when no crawl has finished.
    run_id: int | None = None
    parcels: int = 0
    sales: int = 0
    unparsed: int = 0
    without_mblu: int = 0

    @property
    def failed(self) -> list[CheckResult]:
        return [check for check in self.checks if not check.passed]

    @property
    def written(self) -> bool:
        return self.run_id is not None and not self.failed


def build(session: Session, archive: RawArchive) -> BuildResult:
    run = latest_finished_run(session)
    if run is None:
        return BuildResult()
    run_id = run.id
    pages, unparsed = parse_archive(archive, run)
    current = session.scalar(select(func.count()).select_from(Property)) or 0
    checks = run_checks([page.record for page in pages], current)
    result = BuildResult(checks, current, run_id, unparsed=unparsed)
    for check in result.failed:
        logfire.error(
            "property build check failed: {check}: {detail}",
            check=check.name,
            detail=check.detail,
        )
    if result.failed:
        return result

    # A parcel with no mblu cannot be stored. The core fields check already counted it.
    keyed = [page for page in pages if page.record.mblu]
    sales = replace_properties(session, run, keyed)
    session.commit()
    return BuildResult(
        checks,
        current,
        run_id,
        len(keyed),
        sales,
        unparsed,
        len(pages) - len(keyed),
    )
