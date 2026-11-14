from datetime import UTC, datetime
from pathlib import Path

import pytest
from maintenance.raw_sources import (
    RESTORE_DATABASE,
    CheckReport,
    check,
    main,
    replay_parcels,
    report_lines,
    restore_check,
    version_lines,
)
from mongo.archive import ArchivedResponse, RawArchive
from mongo.client import MongoDB
from pipelines import PropertyPipeline
from postgres.models.pdf_url import PdfUrl
from postgres.models.property import Property
from postgres.models.property_sale import PropertySale
from scrapy.http import HtmlResponse
from spiders.vgsi_property import VgsiPropertySpider
from sqlalchemy import delete, select, update

# The tests folder is not a package pyrefly can follow; pytest imports it from scrapers/.
# pyrefly: ignore[missing-import]
from tests.test_vgsi_property_spider import PARCEL_HTML

PARCEL_URL = "https://gis.vgsi.com/LebanonNH/Parcel.aspx?pid=10001"


def archive_parcel(archive: RawArchive, body: bytes = PARCEL_HTML, day: int = 1):
    archive.add(
        "vgsi_parcel",
        "10001",
        ArchivedResponse(
            url=PARCEL_URL,
            status=200,
            content_type="text/html; charset=utf-8",
            body=body,
            fetched_at=datetime(2026, 11, day, tzinfo=UTC),
            spider="vgsi_property",
        ),
    )
    archive.flush()


def stored_parcel(session) -> tuple:
    session.expire_all()
    row = session.scalars(select(Property)).one()
    sales = session.execute(
        select(PropertySale.sale_date, PropertySale.sale_price, PropertySale.grantee)
    ).all()
    return (row.parcel_id, row.location, row.owner, row.assessed_total, sales)


def ingest_live(session) -> tuple:
    pipeline = PropertyPipeline()
    pipeline.open_spider()
    response = HtmlResponse(url=PARCEL_URL, body=PARCEL_HTML)
    for item in VgsiPropertySpider().parse_parcel(response):
        pipeline.process_item(item)
    pipeline.close_spider()
    return stored_parcel(session)


def clear_parcels(session) -> None:
    session.execute(delete(PropertySale))
    session.execute(delete(Property))
    session.commit()


def test_a_replayed_parcel_matches_a_normal_ingest(db_session, raw_sources):
    from_download = ingest_live(db_session)
    clear_parcels(db_session)
    archive = RawArchive(raw_sources)
    archive_parcel(archive)

    counts = replay_parcels(archive)

    assert stored_parcel(db_session) == from_download
    assert (counts.replayed, counts.inserted) == (1, 1)


def test_replaying_again_leaves_the_parcel_unchanged(db_session, raw_sources):
    archive = RawArchive(raw_sources)
    archive_parcel(archive)
    replay_parcels(archive)

    counts = replay_parcels(archive)

    assert (counts.updated, counts.unchanged) == (0, 1)


def test_a_newer_page_updates_the_parcel(db_session, raw_sources):
    archive = RawArchive(raw_sources)
    archive_parcel(archive)
    replay_parcels(archive)
    archive_parcel(
        archive, PARCEL_HTML.replace(b"SMITH, JOHN</span>", b"DOE</span>"), 2
    )

    counts = replay_parcels(archive)

    assert counts.updated == 1
    assert stored_parcel(db_session)[2] == "DOE"


def set_stored(session, **columns) -> None:
    session.execute(update(Property).values(**columns))
    session.commit()


def stored_property(session) -> Property:
    session.expire_all()
    return session.scalars(select(Property)).one()


def test_a_parcel_stored_after_the_archived_page_is_not_overwritten(
    db_session, raw_sources
):
    # The archive was down for the newer scrape, so its newest page is older than
    # the row. Replaying it would put old data over new.
    ingest_live(db_session)
    set_stored(db_session, owner="NEWER OWNER")
    archive = RawArchive(raw_sources)
    archive_parcel(archive)

    counts = replay_parcels(archive)

    assert stored_property(db_session).owner == "NEWER OWNER"
    assert (counts.replayed, counts.skipped_newer) == (0, 1)


def test_a_parcel_scraped_just_after_its_page_was_archived_is_still_replayed(
    db_session, raw_sources
):
    # A normal scrape archives the page, then the pipeline writes the row a moment later.
    archive = RawArchive(raw_sources)
    archive_parcel(archive)
    replay_parcels(archive)
    set_stored(db_session, owner="OLD OWNER", updated_at=datetime(2026, 11, 1, 0, 5))

    counts = replay_parcels(archive)

    assert stored_property(db_session).owner != "OLD OWNER"
    assert (counts.updated, counts.skipped_newer) == (1, 0)


def test_replay_stamps_the_row_with_the_pages_own_time(db_session, raw_sources):
    archive = RawArchive(raw_sources)
    archive_parcel(archive)

    replay_parcels(archive)

    row = stored_property(db_session)
    assert (row.created_at, row.updated_at) == (datetime(2026, 11, 1),) * 2


def test_a_second_replay_is_not_skipped_by_the_first(db_session, raw_sources):
    # Replay must be repeatable after each parser fix, so its own write cannot make
    # the row look newer than the page.
    archive = RawArchive(raw_sources)
    archive_parcel(archive)
    replay_parcels(archive)
    set_stored(db_session, owner="CHANGED SINCE")

    counts = replay_parcels(archive)

    assert stored_property(db_session).owner != "CHANGED SINCE"
    assert (counts.updated, counts.skipped_newer) == (1, 0)


def test_replay_does_not_write_the_archive(db_session, raw_sources):
    archive = RawArchive(raw_sources)
    archive_parcel(archive)
    before = list(raw_sources.find())

    replay_parcels(archive)

    assert list(raw_sources.find()) == before


def test_missing_and_truncated_versions_have_no_usable_body(
    db_session, raw_sources, monkeypatch
):
    monkeypatch.setattr("mongo.archive.MAX_COMPRESSED_BYTES", 10)
    archive = RawArchive(raw_sources)
    archive_parcel(archive)

    counts = replay_parcels(archive, ["10001", "99999"])

    assert (counts.replayed, counts.no_body) == (0, 2)
    assert db_session.scalars(select(Property)).all() == []


def test_versions_are_listed_newest_first(raw_sources, capsys, monkeypatch):
    archive = RawArchive(raw_sources)
    archive_parcel(archive, day=1)
    archive_parcel(archive, PARCEL_HTML + b"<!-- v2 -->", day=3)

    assert main(["versions", "--source", "vgsi_parcel", "--key", "10001"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert [line[:10] for line in lines] == ["2026-11-03", "2026-11-01"]
    assert "seen 1" in lines[0]


def test_versions_of_an_unknown_key_exit_non_zero(raw_sources, capsys):
    assert main(["versions", "--source", "vgsi_parcel", "--key", "nope"]) == 1
    assert "No versions" in capsys.readouterr().out


def test_a_truncated_version_is_marked():
    version = {
        "first_fetched_at": datetime(2026, 11, 1),
        "content_hash": "ab" * 32,
        "size_bytes": 20_000_000,
        "seen_count": 2,
        "truncated": True,
    }

    [line] = version_lines([version])

    assert line.endswith("seen 2  truncated")
    assert "20,000,000 bytes" in line


# --- check ---


def add_pdf_url(session, url: str, state: str) -> None:
    session.add(
        PdfUrl(canonical_url=url, state=state, created_at=datetime(2026, 11, 1))
    )
    session.commit()


def archive_version(archive: RawArchive, source: str, key: str, body: bytes) -> None:
    archive.add(
        source,
        key,
        ArchivedResponse(
            url=key,
            status=200,
            content_type=None,
            body=body,
            fetched_at=datetime(2026, 11, 1, tzinfo=UTC),
            spider="test",
        ),
    )
    archive.flush()


@pytest.fixture
def mixed_archive(db_session, raw_sources) -> RawArchive:
    """Log PDFs in every state the check reports, and two parcels."""
    archive = RawArchive(raw_sources)
    for url, state in (
        ("https://x/body", "complete"),
        ("https://x/missing", "error"),
        ("https://x/pending", "pending"),
    ):
        add_pdf_url(db_session, url, state)
    archive_version(archive, "police_log_pdf", "https://x/body", b"%PDF body")
    archive_parcel(archive)
    db_session.add(
        Property(
            parcel_id="10001",
            created_at=datetime(2026, 11, 1),
            updated_at=datetime(2026, 11, 1),
        )
    )
    db_session.add(
        Property(
            parcel_id="20002",
            created_at=datetime(2026, 11, 1),
            updated_at=datetime(2026, 11, 1),
        )
    )
    db_session.commit()
    return archive


def test_check_sorts_finished_log_pdfs_by_what_the_archive_holds(
    db_session, raw_sources, mixed_archive
):
    report = check(raw_sources, db_session)

    assert report.pdfs_with_body == 1
    assert report.pdfs_without_body == ["https://x/missing"]
    assert report.parcels_without_version == ["20002"]
    assert report.every_pdf_has_a_body is False


def test_check_counts_versions_and_size_per_source(
    db_session, raw_sources, mixed_archive
):
    report = check(raw_sources, db_session)

    by_source = {s.source: (s.versions, s.size_bytes) for s in report.sources}
    assert by_source["police_log_pdf"] == (1, len(b"%PDF body"))
    assert by_source["vgsi_parcel"] == (1, len(PARCEL_HTML))
    assert report.storage_bytes > 0


def test_a_truncated_pdf_does_not_count_as_a_body(db_session, raw_sources, monkeypatch):
    monkeypatch.setattr("mongo.archive.MAX_COMPRESSED_BYTES", 10)
    add_pdf_url(db_session, "https://x/big", "complete")
    archive_version(
        RawArchive(raw_sources), "police_log_pdf", "https://x/big", b"x" * 500
    )

    report = check(raw_sources, db_session)

    assert report.pdfs_without_body == ["https://x/big"]


def test_the_check_command_fails_while_a_pdf_has_no_body(
    db_session, raw_sources, mixed_archive, capsys
):
    assert main(["check"]) == 1

    out = capsys.readouterr().out
    assert "1 with an archived body, 1 without one" in out
    assert "  no body: https://x/missing" in out


def test_the_check_command_passes_when_every_pdf_has_one(
    db_session, raw_sources, capsys
):
    add_pdf_url(db_session, "https://x/body", "complete")
    archive_version(RawArchive(raw_sources), "police_log_pdf", "https://x/body", b"b")

    assert main(["check"]) == 0


def test_a_size_past_five_gb_is_warned_about(monkeypatch):
    report = CheckReport(
        sources=[],
        storage_bytes=6 * 1024**3,
        pdfs_with_body=0,
        pdfs_without_body=[],
        parcels_without_version=[],
    )

    assert "Warning: the archive has passed 5 GB." in report_lines(report)


# --- restore-check ---


class FakeRestore:
    """Stands in for mongorestore: copies the live archive into the restore database."""

    def __init__(self, raw_sources, returncode: int = 0, copy: bool = True) -> None:
        self.raw_sources = raw_sources
        self.returncode = returncode
        self.copy = copy
        self.commands: list[list[str]] = []

    def __call__(self, command) -> int:
        self.commands.append(list(command))
        if self.copy:
            target = self.raw_sources.database.client[RESTORE_DATABASE]["raw_sources"]
            target.insert_many(list(self.raw_sources.find()))
        return self.returncode


@pytest.fixture
def backup_file(tmp_path) -> Path:
    path = tmp_path / "scraped_data_test-20261107T020000Z.archive.gz"
    path.write_bytes(b"dump")
    return path


def restored_databases(raw_sources) -> list[str]:
    return [
        name
        for name in raw_sources.database.client.list_database_names()
        if name == RESTORE_DATABASE
    ]


def test_a_complete_backup_passes_and_its_restore_is_dropped(raw_sources, backup_file):
    archive_parcel(RawArchive(raw_sources))
    restore = FakeRestore(raw_sources)

    problems = restore_check(backup_file, MongoDB(), restore)

    assert problems == []
    [command] = restore.commands
    assert command[0] == "mongorestore"
    assert "--nsFrom=scraped_data_test.*" in command
    assert f"--nsTo={RESTORE_DATABASE}.*" in command
    assert restored_databases(raw_sources) == []


def test_a_backup_missing_the_archive_fails(raw_sources, backup_file):
    archive_parcel(RawArchive(raw_sources))

    problems = restore_check(
        backup_file, MongoDB(), FakeRestore(raw_sources, copy=False)
    )

    assert problems == ["raw_sources has no documents in the backup."]


def test_a_failed_restore_fails(raw_sources, backup_file):
    restore = FakeRestore(raw_sources, returncode=1, copy=False)

    assert restore_check(backup_file, MongoDB(), restore) == [
        "mongorestore exited with status 1."
    ]


def test_a_missing_backup_file_fails(tmp_path):
    missing = tmp_path / "none.archive.gz"

    assert restore_check(missing, MongoDB(), FakeRestore(None)) == [
        f"No backup at {missing}."
    ]


def test_a_restore_never_targets_the_live_database(backup_file, monkeypatch):
    monkeypatch.setenv("MONGO_DB", RESTORE_DATABASE)
    restore = FakeRestore(None)

    problems = restore_check(backup_file, MongoDB(), restore)

    assert problems == [
        f"Refusing to restore over {RESTORE_DATABASE}: it is the live database."
    ]
    assert restore.commands == []
