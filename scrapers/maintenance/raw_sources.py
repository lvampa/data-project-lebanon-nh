"""Operator commands for the raw source archive.

Run from scrapers/:

    uv run python -m maintenance.raw_sources versions --source SOURCE --key KEY
    uv run python -m maintenance.raw_sources check
    uv run python -m maintenance.raw_sources restore-check BACKUP

Parcel pages are parsed by `maintenance.build_properties`, and police log PDFs by the
police log reprocess job.
"""

import argparse
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import logfire
from bootstrap import bootstrap
from mongo.archive import RawArchive, RawCollection, archive_collection
from mongo.client import MongoDB, get_db
from postgres import open_session
from postgres.models.pdf_url import PdfUrl
from postgres.models.property import Property
from sqlalchemy import select
from sqlalchemy.orm import Session

from maintenance.mongo_backup import Runner, run_tool

PARCEL_SOURCE = "vgsi_parcel"
PDF_SOURCE = "police_log_pdf"
SIZE_WARNING_BYTES = 5 * 1024**3
RESTORE_DATABASE = "scraped_data_restore_test"


@dataclass(frozen=True)
class SourceSize:
    source: str
    versions: int
    # Bodies as downloaded, before compression.
    size_bytes: int


@dataclass(frozen=True)
class CheckReport:
    sources: list[SourceSize]
    storage_bytes: int
    pdfs_with_body: int
    pdfs_without_body: list[str]
    parcels_without_version: list[str]

    @property
    def every_pdf_has_a_body(self) -> bool:
        """Every finished log PDF has its original in the archive."""
        return not self.pdfs_without_body


def check(collection: RawCollection, session: Session) -> CheckReport:
    """What the archive holds, and which Postgres records it has no original for."""
    sources = [
        SourceSize(row["_id"], row["versions"], row["size_bytes"])
        for row in collection.aggregate(
            [
                {
                    "$group": {
                        "_id": "$source",
                        "versions": {"$sum": 1},
                        "size_bytes": {"$sum": "$size_bytes"},
                    }
                },
                {"$sort": {"_id": 1}},
            ]
        )
    ]
    bodies = set(
        collection.distinct("source_key", {"source": PDF_SOURCE, "truncated": False})
    )
    parcels = set(collection.distinct("source_key", {"source": PARCEL_SOURCE}))

    finished_pdfs = session.scalars(
        select(PdfUrl.canonical_url)
        .where(PdfUrl.state.in_(("complete", "error")))
        .order_by(PdfUrl.canonical_url)
    ).all()
    parcel_ids = session.scalars(
        select(Property.vgsi_pid).order_by(Property.vgsi_pid)
    ).all()

    report = CheckReport(
        sources=sources,
        storage_bytes=_storage_bytes(collection),
        pdfs_with_body=sum(url in bodies for url in finished_pdfs),
        pdfs_without_body=[u for u in finished_pdfs if u not in bodies],
        parcels_without_version=[p for p in parcel_ids if p not in parcels],
    )
    if report.storage_bytes > SIZE_WARNING_BYTES:
        logfire.warning("raw archive passed 5 GB", storage_bytes=report.storage_bytes)
    return report


def _storage_bytes(collection: RawCollection) -> int:
    stats = next(collection.aggregate([{"$collStats": {"storageStats": {}}}]), None)
    return stats["storageStats"]["storageSize"] if stats else 0


def report_lines(report: CheckReport) -> list[str]:
    lines = [f"Archive storage: {report.storage_bytes:,} bytes."]
    if report.storage_bytes > SIZE_WARNING_BYTES:
        lines.append("Warning: the archive has passed 5 GB.")
    lines += [
        f"  {s.source}: {s.versions} versions, {s.size_bytes:,} bytes uncompressed"
        for s in report.sources
    ]
    lines.append(
        f"Log PDFs: {report.pdfs_with_body} with an archived body, "
        f"{len(report.pdfs_without_body)} without one."
    )
    lines += [f"  no body: {url}" for url in report.pdfs_without_body]
    lines.append(
        f"Parcels with no archived version: {len(report.parcels_without_version)}."
    )
    lines += [f"  {pid}" for pid in report.parcels_without_version]
    return lines


def restore_check(backup: Path, settings: MongoDB, run: Runner) -> list[str]:
    """Restore a backup into a test database and compare it with the live one.

    Returns the problems found; an empty list means the backup is usable. The live
    database only grows, so a restored collection may hold fewer documents.
    """
    if settings.default_db == RESTORE_DATABASE:
        return [
            f"Refusing to restore over {RESTORE_DATABASE}: it is the live database."
        ]
    if not backup.is_file():
        return [f"No backup at {backup}."]
    returncode = run_tool(
        "mongorestore",
        settings,
        [
            "--gzip",
            f"--archive={backup}",
            f"--nsFrom={settings.default_db}.*",
            f"--nsTo={RESTORE_DATABASE}.*",
            "--drop",
        ],
        run,
    )
    if returncode != 0:
        return [f"mongorestore exited with status {returncode}."]

    live = settings.get_collection(PDF_SOURCE).database
    restored = settings.get_collection(PDF_SOURCE, db=RESTORE_DATABASE).database
    problems = []
    try:
        for name in sorted(live.list_collection_names()):
            live_count = live[name].count_documents({})
            restored_count = restored[name].count_documents({})
            print(f"  {name}: {restored_count} restored, {live_count} live")
            if live_count and not restored_count:
                problems.append(f"{name} has no documents in the backup.")
            elif restored_count > live_count:
                problems.append(f"{name} has more documents in the backup than live.")
    finally:
        restored.client.drop_database(RESTORE_DATABASE)
    return problems


def _run(command: Sequence[str]) -> int:
    return subprocess.run(command, check=False).returncode


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
    bootstrap("raw-sources")
    parser = argparse.ArgumentParser(prog="raw_sources")
    commands = parser.add_subparsers(dest="command", required=True)

    versions = commands.add_parser("versions", help="List one key's versions.")
    versions.add_argument("--source", required=True)
    versions.add_argument("--key", required=True)

    commands.add_parser("check", help="Report what the archive holds and lacks.")

    restore = commands.add_parser(
        "restore-check", help=f"Restore a backup into {RESTORE_DATABASE}."
    )
    restore.add_argument("backup", type=Path)

    args = parser.parse_args(argv)
    settings = get_db()

    if args.command == "restore-check":
        problems = restore_check(args.backup, settings, _run)
        print("\n".join(problems) or f"{args.backup} restores and looks complete.")
        return 1 if problems else 0

    collection = archive_collection(settings)
    if args.command == "check":
        with open_session() as session:
            report = check(collection, session)
        print("\n".join(report_lines(report)))
        return 0 if report.every_pdf_has_a_body else 1

    archive = RawArchive(collection)

    found = archive.versions(args.source, args.key)
    if not found:
        print(f"No versions of {args.source} {args.key}.")
        return 1
    print("\n".join(version_lines(found)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
