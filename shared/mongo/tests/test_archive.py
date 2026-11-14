import gzip
import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from mongo.archive import (
    ArchiveCounts,
    ArchivedResponse,
    RawArchive,
    RawCollection,
    archive_collection,
    content_hash,
    stored_body,
    version_insert,
)
from mongo.client import MongoDB
from pymongo.errors import OperationFailure

PDF = b"%PDF-1.4 a police log"


def response(body: bytes = PDF, **overrides: Any) -> ArchivedResponse:
    original = ArchivedResponse(
        url="https://www.lebanonnh.gov/DocumentCenter/View/23007/2026-05-11",
        status=200,
        content_type="application/pdf",
        body=body,
        fetched_at=datetime(2026, 11, 6, 12, 0, tzinfo=UTC),
        spider="process_urls",
    )
    return replace(original, **overrides)


def parcel_page(view_state: str) -> bytes:
    return (
        '<form><input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" '
        f'value="{view_state}" /><input type="hidden" name="__EVENTVALIDATION" '
        f'value="{view_state}x" /><span id="MainContent_lblLocation">1 MAIN ST</span>'
        "</form>"
    ).encode()


def stored(raw_sources, source: str = "police_log_pdf") -> list[dict]:
    return list(raw_sources.find({"source": source}).sort("first_fetched_at", 1))


def test_a_new_body_is_stored_compressed_with_where_it_came_from(raw_sources):
    archive = RawArchive(raw_sources)

    archive.add("police_log_pdf", "https://example.com/a", response())
    counts = archive.flush()

    assert counts == ArchiveCounts(stored=1, seen_again=0, failed=0)
    [version] = stored(raw_sources)
    assert gzip.decompress(version["body_gzip"]) == PDF
    assert version["source_key"] == "https://example.com/a"
    assert version["url"].endswith("/2026-05-11")
    assert (version["status"], version["content_type"]) == (200, "application/pdf")
    assert version["size_bytes"] == len(PDF)
    assert version["content_hash"] == content_hash("police_log_pdf", PDF)
    assert version["seen_count"] == 1
    assert version["truncated"] is False
    assert version["spider"] == "process_urls"


def test_the_same_body_again_is_counted_not_stored_twice(raw_sources):
    archive = RawArchive(raw_sources)
    archive.add("police_log_pdf", "https://example.com/a", response())
    archive.flush()

    later = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    archive.add("police_log_pdf", "https://example.com/a", response(fetched_at=later))
    counts = archive.flush()

    assert counts == ArchiveCounts(stored=1, seen_again=1, failed=0)
    [version] = stored(raw_sources)
    assert version["seen_count"] == 2
    assert version["last_seen_at"].replace(tzinfo=UTC) == later


def test_a_changed_body_is_a_new_version_and_the_old_one_stays(raw_sources):
    archive = RawArchive(raw_sources)
    archive.add("police_log_pdf", "https://example.com/a", response(PDF))
    archive.add("police_log_pdf", "https://example.com/a", response(PDF + b" v2"))
    archive.flush()

    assert [gzip.decompress(v["body_gzip"]) for v in stored(raw_sources)] == [
        PDF,
        PDF + b" v2",
    ]


def test_parcel_page_state_fields_do_not_make_a_new_version(raw_sources):
    archive = RawArchive(raw_sources)
    for view_state in ("first", "second"):
        archive.add("vgsi_parcel", "1000", response(parcel_page(view_state)))
    archive.flush()

    [version] = stored(raw_sources, "vgsi_parcel")
    assert version["seen_count"] == 2
    # The body itself is stored as downloaded, page state included.
    assert b"first" in gzip.decompress(version["body_gzip"])


def test_page_state_is_ignored_only_for_parcel_pages():
    assert content_hash("vgsi_parcel", parcel_page("a")) == content_hash(
        "vgsi_parcel", parcel_page("b")
    )
    assert content_hash("police_log_pdf", parcel_page("a")) != content_hash(
        "police_log_pdf", parcel_page("b")
    )


def test_an_oversized_body_is_stored_without_it_and_marked(raw_sources, monkeypatch):
    monkeypatch.setattr("mongo.archive.MAX_COMPRESSED_BYTES", 10)
    archive = RawArchive(raw_sources)

    archive.add("police_log_pdf", "https://example.com/a", response(PDF * 50))
    archive.flush()

    [version] = stored(raw_sources)
    assert version["truncated"] is True
    assert "body_gzip" not in version
    assert version["size_bytes"] == len(PDF * 50)


def test_a_full_batch_is_written_without_waiting_for_flush(raw_sources):
    archive = RawArchive(raw_sources, batch_size=2)

    archive.add("police_log_pdf", "https://example.com/a", response(PDF + b"1"))
    archive.add("police_log_pdf", "https://example.com/b", response(PDF + b"2"))

    assert raw_sources.count_documents({}) == 2


def test_add_says_whether_the_write_worked_once_the_batch_is_full(raw_sources):
    archive = RawArchive(raw_sources, batch_size=2)

    assert archive.add("police_log_pdf", "https://example.com/a", response()) is None
    assert archive.add("police_log_pdf", "https://example.com/b", response()) is True


def test_with_a_batch_of_one_each_add_is_written_and_reported(raw_sources):
    archive = RawArchive(
        cast(RawCollection, FailingCollection(raw_sources)), batch_size=1
    )

    assert archive.add("police_log_pdf", "https://example.com/a", response()) is False
    assert archive.add("police_log_pdf", "https://example.com/b", response()) is True
    assert raw_sources.count_documents({}) == 1


class FailingCollection:
    """Stands in for a collection whose writes fail, as on a full disk."""

    def __init__(self, real) -> None:
        self.real = real
        self.failures_left = 1

    def bulk_write(self, operations, ordered: bool):
        if self.failures_left:
            self.failures_left -= 1
            raise OperationFailure("disk full")
        return self.real.bulk_write(operations, ordered=ordered)


def test_a_failed_batch_is_counted_and_later_batches_still_try(raw_sources):
    archive = RawArchive(cast(RawCollection, FailingCollection(raw_sources)))

    archive.add("police_log_pdf", "https://example.com/a", response(PDF + b"1"))
    archive.flush()
    archive.add("police_log_pdf", "https://example.com/b", response(PDF + b"2"))
    counts = archive.flush()

    assert counts == ArchiveCounts(stored=1, seen_again=0, failed=1)
    assert archive.is_down is False
    assert raw_sources.count_documents({}) == 1


def unused_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def archive_at(port: int, monkeypatch) -> RawArchive:
    monkeypatch.setenv("MONGO_HOST", "127.0.0.1")
    monkeypatch.setenv("MONGO_PORT", str(port))
    return RawArchive(archive_collection(MongoDB()))


def test_an_unreachable_server_marks_the_archive_down_after_one_try(monkeypatch):
    archive = archive_at(unused_port(), monkeypatch)

    archive.add("police_log_pdf", "https://example.com/a", response())
    first_try = time.monotonic()
    archive.flush()
    assert time.monotonic() - first_try < 5
    assert archive.is_down is True

    archive.add("police_log_pdf", "https://example.com/b", response(PDF + b"2"))
    second_try = time.monotonic()
    counts = archive.flush()

    # Once down, later batches are dropped without waiting on the server again.
    assert time.monotonic() - second_try < 0.5
    assert counts == ArchiveCounts(stored=0, seen_again=0, failed=2)


def test_once_down_a_batch_of_one_reports_each_write_failed(monkeypatch):
    monkeypatch.setenv("MONGO_HOST", "127.0.0.1")
    monkeypatch.setenv("MONGO_PORT", str(unused_port()))
    archive = RawArchive(archive_collection(MongoDB()), batch_size=1)

    assert archive.add("police_log_pdf", "https://example.com/a", response()) is False
    assert archive.add("police_log_pdf", "https://example.com/b", response()) is False
    assert archive.flush().failed == 2


@pytest.fixture
def hung_server() -> Iterator[int]:
    """A server that accepts connections and never answers."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    held: list[socket.socket] = []
    stop = threading.Event()

    def accept() -> None:
        listener.settimeout(0.2)
        while not stop.is_set():
            try:
                connection, _ = listener.accept()
            except TimeoutError:
                continue
            held.append(connection)

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    yield listener.getsockname()[1]
    stop.set()
    thread.join()
    for connection in held:
        connection.close()
    listener.close()


def test_a_server_that_hangs_marks_the_archive_down(hung_server, monkeypatch):
    archive = archive_at(hung_server, monkeypatch)

    archive.add("police_log_pdf", "https://example.com/a", response())
    started = time.monotonic()
    counts = archive.flush()

    assert time.monotonic() - started < 10
    assert archive.is_down is True
    assert counts.failed == 1


def test_newest_and_by_hash_find_the_right_one_of_two_versions(raw_sources):
    archive = RawArchive(raw_sources)
    first = response(PDF + b" v1", fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    second = response(PDF + b" v2", fetched_at=datetime(2026, 11, 2, tzinfo=UTC))
    archive.add("police_log_pdf", "https://example.com/a", first)
    archive.add("police_log_pdf", "https://example.com/a", second)
    archive.add("police_log_pdf", "https://example.com/b", response())
    archive.flush()

    newest = archive.newest("police_log_pdf", "https://example.com/a")
    older = archive.by_hash(
        "police_log_pdf",
        "https://example.com/a",
        content_hash("police_log_pdf", PDF + b" v1"),
    )

    assert newest is not None and stored_body(newest) == PDF + b" v2"
    assert older is not None and stored_body(older) == PDF + b" v1"
    assert archive.newest("police_log_pdf", "https://example.com/none") is None


def test_versions_lists_one_key_newest_first(raw_sources):
    archive = RawArchive(raw_sources)
    for day in (1, 3, 2):
        archive.add(
            "vgsi_parcel",
            "1000",
            response(
                parcel_page(f"day {day}") + f"day {day}".encode(),
                fetched_at=datetime(2026, 11, day, tzinfo=UTC),
            ),
        )
    archive.add("vgsi_parcel", "2000", response(parcel_page("x")))
    archive.flush()

    versions = archive.versions("vgsi_parcel", "1000")

    assert [v["first_fetched_at"].day for v in versions] == [3, 2, 1]


def test_a_truncated_version_has_no_body(raw_sources, monkeypatch):
    monkeypatch.setattr("mongo.archive.MAX_COMPRESSED_BYTES", 10)
    archive = RawArchive(raw_sources)
    archive.add("police_log_pdf", "https://example.com/a", response(PDF * 50))
    archive.flush()

    version = archive.newest("police_log_pdf", "https://example.com/a")

    assert version is not None and stored_body(version) is None


def test_extracted_text_is_kept_beside_the_body(raw_sources):
    archive = RawArchive(raw_sources)

    archive.add("budget_pdf", "https://example.com/b.pdf", response(text="FY27 budget"))
    archive.flush()

    [version] = stored(raw_sources, "budget_pdf")
    assert gzip.decompress(version["text_gzip"]) == b"FY27 budget"
    assert gzip.decompress(version["body_gzip"]) == PDF


def test_no_text_field_without_extracted_text(raw_sources):
    archive = RawArchive(raw_sources)
    archive.add("police_log_pdf", "https://example.com/a", response())
    archive.flush()

    [version] = stored(raw_sources)
    assert "text_gzip" not in version


def test_keys_lists_each_source_key_once(raw_sources):
    archive = RawArchive(raw_sources)
    for key, body in (("2000", b"a"), ("1000", b"b"), ("1000", b"c")):
        archive.add("vgsi_parcel", key, response(body))
    archive.add("police_log_pdf", "https://example.com/a", response())
    archive.flush()

    assert archive.keys("vgsi_parcel") == ["1000", "2000"]


def test_an_insert_only_write_leaves_a_stored_version_as_it_is(raw_sources):
    first = response(fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    again = response(fetched_at=datetime(2026, 11, 2, tzinfo=UTC))
    raw_sources.bulk_write([version_insert("police_log_entry_text", "k", first)])
    [before] = stored(raw_sources, "police_log_entry_text")

    raw_sources.bulk_write([version_insert("police_log_entry_text", "k", again)])

    [after] = stored(raw_sources, "police_log_entry_text")
    assert after == before
    assert (after["seen_count"], after["last_seen_at"].day) == (1, 1)
