from unittest.mock import MagicMock, patch

from items import PoliceLogItem
from scrapy.http import Request, Response
from spiders.process_url_records import ProcessUrlsSpider

FAKE_PDF = b"%PDF-1.4 fake pdf content"

SAMPLE_TEXT = """\
 Lebanon Police Department Page:   1
  Dispatch Log  From: 05/01/2026  Thru: 05/01/2026     0000 - 2359    Printed: 05/04/2026
For Date: 05/01/2026  -  Friday
Call   Number   Time   Call   Reason   Action
26-13339        0106 Phone - Telephone Harassment Incident Report Taken
       Call Source:    Telephone
        Primary Id:    SMN - Officer Stephan Nix
  Location/Address:    TIMBERWOOD DR
"""


def make_response(url: str, body: bytes) -> Response:
    return Response(url=url, body=body)


@patch("spiders.process_url_records.PdfReader")
@patch("spiders.process_url_records.db")
def test_parse_yields_police_log_items(mock_db, mock_pdf_reader):
    mock_page = MagicMock()
    mock_page.extract_text.return_value = SAMPLE_TEXT
    mock_pdf_reader.return_value.pages = [mock_page]

    spider = ProcessUrlsSpider.__new__(ProcessUrlsSpider)
    url_doc = MagicMock()
    url_doc.canonical_url = "https://example.com/a.pdf"
    url_doc.archive_url = None

    response = make_response("https://example.com/a.pdf", FAKE_PDF)
    items = list(spider.parse(response, url_doc=url_doc))

    assert len(items) == 1
    assert isinstance(items[0], PoliceLogItem)
    assert items[0]["source_url"] == "https://example.com/a.pdf"
    assert items[0]["parse_error"] is False
    # raw_text is the per-entry block, not the full PDF text
    assert "26-13339" in items[0]["raw_text"]


@patch("spiders.process_url_records.PdfReader")
@patch("spiders.process_url_records.db")
def test_parse_sets_entry_count_and_state_on_mongo(mock_db, mock_pdf_reader):
    mock_page = MagicMock()
    mock_page.extract_text.return_value = SAMPLE_TEXT
    mock_pdf_reader.return_value.pages = [mock_page]

    spider = ProcessUrlsSpider.__new__(ProcessUrlsSpider)
    url_doc = MagicMock()
    url_doc.canonical_url = "https://example.com/a.pdf"
    url_doc.archive_url = None

    response = make_response("https://example.com/a.pdf", FAKE_PDF)
    list(spider.parse(response, url_doc=url_doc))

    update_call = mock_db.get_collection.return_value.update_one.call_args
    set_doc = update_call[0][1]["$set"]
    assert set_doc["state"] == "complete"
    assert set_doc["entry_count"] == 1
    assert "raw_text" in set_doc
    assert "completed_at" in set_doc


@patch("spiders.process_url_records.db")
def test_parse_non_pdf_with_archive_url_yields_fallback_request(mock_db):
    spider = ProcessUrlsSpider.__new__(ProcessUrlsSpider)
    url_doc = MagicMock()
    url_doc.canonical_url = "https://example.com/a.pdf"
    url_doc.archive_url = (
        "https://web.archive.org/web/20191015/https://example.com/a.pdf"
    )

    response = make_response("https://example.com/a.pdf", b"<html>not a pdf</html>")
    results = list(spider.parse(response, url_doc=url_doc))

    assert len(results) == 1
    assert isinstance(results[0], Request)
    assert results[0].url == url_doc.archive_url


@patch("spiders.process_url_records.db")
def test_parse_non_pdf_without_archive_url_marks_mongo_error(mock_db):
    spider = ProcessUrlsSpider.__new__(ProcessUrlsSpider)
    url_doc = MagicMock()
    url_doc.canonical_url = "https://example.com/a.pdf"
    url_doc.archive_url = None

    response = make_response("https://example.com/a.pdf", b"<html>not a pdf</html>")
    results = list(spider.parse(response, url_doc=url_doc))

    assert results == []
    update_call = mock_db.get_collection.return_value.update_one.call_args
    set_doc = update_call[0][1]["$set"]
    assert set_doc["state"] == "error"
    assert "error_message" in set_doc


@patch("spiders.process_url_records.PdfReader")
@patch("spiders.process_url_records.db")
def test_parse_no_entries_marks_mongo_error_and_yields_nothing(
    mock_db, mock_pdf_reader
):
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "No date header here, will not parse"
    mock_pdf_reader.return_value.pages = [mock_page]

    spider = ProcessUrlsSpider.__new__(ProcessUrlsSpider)
    url_doc = MagicMock()
    url_doc.canonical_url = "https://example.com/a.pdf"
    url_doc.archive_url = None

    response = make_response("https://example.com/a.pdf", FAKE_PDF)
    items = list(spider.parse(response, url_doc=url_doc))

    assert items == []
    update_call = mock_db.get_collection.return_value.update_one.call_args
    set_doc = update_call[0][1]["$set"]
    assert set_doc["state"] == "error"
    assert set_doc["entry_count"] == 0
    assert "error_message" in set_doc
    assert "raw_text" in set_doc
