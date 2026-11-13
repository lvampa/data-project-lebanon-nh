from datetime import UTC, datetime

from maintenance.raw_sources import main, replay_parcels, version_lines
from mongo.archive import ArchivedResponse, RawArchive
from pipelines import PropertyPipeline
from postgres.models.property import Property
from postgres.models.property_sale import PropertySale
from scrapy.http import HtmlResponse
from spiders.vgsi_property import VgsiPropertySpider
from sqlalchemy import delete, select

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
