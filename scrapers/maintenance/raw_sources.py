"""Operator commands for the raw source archive.

Run from scrapers/:

    uv run python -m maintenance.raw_sources replay --source vgsi_parcel [--parcel PID ...]
    uv run python -m maintenance.raw_sources versions --source SOURCE --key KEY

Police log PDFs are not replayed here; the police log reprocess job reads them.
"""

import argparse
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import logfire
from mongo.archive import RawArchive, archive_collection, stored_body
from mongo.client import MongoDB
from pipelines import PropertyPipeline
from postgres import SessionLocal
from postgres.models.property import Property
from postgres.models.property_sale import PropertySale
from scrapy.http import HtmlResponse
from spiders.vgsi_property import VgsiPropertySpider
from sqlalchemy import select
from sqlalchemy.orm import Session

PARCEL_SOURCE = "vgsi_parcel"

# Parsed values only; timestamps move on every upsert.
_PROPERTY_FIELDS = (
    "location",
    "owner",
    "owner_address",
    "land_use",
    "lot_size_acres",
    "year_built",
    "building_sqft",
    "assessed_land",
    "assessed_building",
    "assessed_total",
    "assessment_year",
    "detail_url",
)


@dataclass(frozen=True)
class ReplayCounts:
    replayed: int
    inserted: int
    updated: int
    unchanged: int
    no_body: int
    # Parcels whose stored row is newer than the newest archived page, left alone.
    skipped_newer: int = 0


# A normal scrape archives a page and writes its row moments later. A row newer than
# its page by more than this was written by a scrape the archive missed, such as while
# MongoDB was down, so replaying the older page would put old data over new.
REPLAY_GRACE = timedelta(hours=1)


def replay_parcels(
    archive: RawArchive, parcel_ids: Sequence[str] | None = None
) -> ReplayCounts:
    """Parse each parcel's newest archived page and store it, without downloading.

    Reads the archive and never writes it. A parcel whose stored row is newer than its
    newest archived page is skipped. Each replayed row is stamped with its page's own
    time, so a later replay, after another parser fix, is not skipped by this one.
    """
    keys = parcel_ids or archive.keys(PARCEL_SOURCE)
    spider = VgsiPropertySpider()
    pipeline = PropertyPipeline()
    pipeline.open_spider()
    replayed = inserted = updated = unchanged = no_body = skipped_newer = 0
    try:
        for parcel_id in keys:
            page = _newest_page(archive, parcel_id)
            if page is None:
                no_body += 1
                continue
            response, page_time = page
            stored_at = _stored_updated_at(parcel_id)
            if stored_at is not None and stored_at > page_time + REPLAY_GRACE:
                skipped_newer += 1
                continue
            pipeline.clock = lambda stamp=page_time: stamp
            before = _stored_parcel(parcel_id)
            for item in spider.parse_parcel(response):
                pipeline.process_item(item)
            after = _stored_parcel(parcel_id)
            replayed += 1
            if before is None:
                inserted += 1
            elif before != after:
                updated += 1
            else:
                unchanged += 1
    finally:
        pipeline.close_spider()
    counts = ReplayCounts(
        replayed, inserted, updated, unchanged, no_body, skipped_newer
    )
    logfire.info(
        "parcels replayed",
        replayed=counts.replayed,
        inserted=counts.inserted,
        updated=counts.updated,
        unchanged=counts.unchanged,
        no_body=counts.no_body,
        skipped_newer=counts.skipped_newer,
    )
    return counts


def _newest_page(
    archive: RawArchive, parcel_id: str
) -> tuple[HtmlResponse, datetime] | None:
    """The newest archived page, and when the archive last saw it (naive UTC)."""
    version = archive.newest(PARCEL_SOURCE, parcel_id)
    body = stored_body(version) if version is not None else None
    if version is None or body is None:
        return None
    seen_at = version.get("last_seen_at") or version["first_fetched_at"]
    if seen_at.tzinfo is not None:
        seen_at = seen_at.astimezone(UTC).replace(tzinfo=None)
    response = HtmlResponse(url=version["url"], body=body, encoding="utf-8")
    return response, seen_at


def _stored_updated_at(parcel_id: str) -> datetime | None:
    with SessionLocal() as session:
        return session.scalar(
            select(Property.updated_at).where(Property.parcel_id == parcel_id)
        )


def _stored_parcel(parcel_id: str) -> tuple[Any, ...] | None:
    # A short session per read, so it never spans the pipeline's own commit.
    with SessionLocal() as session:
        return _parcel_values(session, parcel_id)


def _parcel_values(session: Session, parcel_id: str) -> tuple[Any, ...] | None:
    row = session.scalars(
        select(Property).where(Property.parcel_id == parcel_id)
    ).one_or_none()
    if row is None:
        return None
    sales = session.execute(
        select(
            PropertySale.sale_date,
            PropertySale.sale_price,
            PropertySale.grantee,
            PropertySale.grantor,
        )
        .where(PropertySale.property_id == row.id)
        .order_by(PropertySale.sale_date, PropertySale.grantee)
    ).all()
    return (*(getattr(row, field) for field in _PROPERTY_FIELDS), tuple(sales))


def version_lines(versions: Iterable[dict[str, Any]]) -> list[str]:
    """One line per version: fetch time, content hash, size, and seen count."""
    lines = []
    for version in versions:
        truncated = "  truncated" if version.get("truncated") else ""
        lines.append(
            f"{version['first_fetched_at']:%Y-%m-%d %H:%M}  "
            f"{version['content_hash'][:12]}  "
            f"{version['size_bytes']:>10,} bytes  "
            f"seen {version['seen_count']}{truncated}"
        )
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="raw_sources")
    commands = parser.add_subparsers(dest="command", required=True)

    replay = commands.add_parser("replay", help="Rebuild records from archived pages.")
    replay.add_argument("--source", required=True, choices=[PARCEL_SOURCE])
    replay.add_argument("--parcel", action="append", help="A parcel ID; repeatable.")

    versions = commands.add_parser("versions", help="List one key's versions.")
    versions.add_argument("--source", required=True)
    versions.add_argument("--key", required=True)

    args = parser.parse_args(argv)
    archive = RawArchive(archive_collection(MongoDB()))

    if args.command == "replay":
        counts = replay_parcels(archive, args.parcel)
        print(
            f"Replayed {counts.replayed} parcels: {counts.inserted} inserted, "
            f"{counts.updated} updated, {counts.unchanged} unchanged. "
            f"{counts.no_body} had no usable body, and "
            f"{counts.skipped_newer} were newer than their archived page."
        )
        return 0

    found = archive.versions(args.source, args.key)
    if not found:
        print(f"No versions of {args.source} {args.key}.")
        return 1
    print("\n".join(version_lines(found)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
