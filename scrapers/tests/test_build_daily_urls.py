from scrapy.http import HtmlResponse

from items import UrlRecordItem
from spiders.create_url_records import BuildDailyUrlsSpider


def make_selector(href: str | None, base_url: str = "https://www.example.com/"):
    inner = f'href="{href}"' if href else ""
    html = f'<a class="fileType pdf " {inner}>Log</a>'.encode()
    return HtmlResponse(url=base_url, body=html).css("a")[0]


def make_response(
    hrefs: list[str], base_url: str = "https://www.example.com"
) -> HtmlResponse:
    links = "".join(f'<a class="fileType pdf " href="{href}">Log</a>' for href in hrefs)
    return HtmlResponse(
        url=base_url, body=f"<html><body>{''.join(links)}</body></html>".encode()
    )


# --- extract_url ---


def test_extract_url_relative():
    sel = make_selector("/documents/file.pdf")
    assert BuildDailyUrlsSpider.extract_url(sel, "https://www.example.com/") == (
        "https://www.example.com/documents/file.pdf",
        None,
    )


def test_extract_url_absolute():
    sel = make_selector("https://other.com/file.pdf")
    assert BuildDailyUrlsSpider.extract_url(sel, "https://www.example.com/") == (
        "https://other.com/file.pdf",
        None,
    )


def test_extract_url_strips_query_and_fragment():
    sel = make_selector("/file.pdf?v=1&token=abc#section")
    assert BuildDailyUrlsSpider.extract_url(sel, "https://www.example.com/") == (
        "https://www.example.com/file.pdf",
        None,
    )


def test_extract_url_no_href():
    sel = make_selector(None)
    assert BuildDailyUrlsSpider.extract_url(sel, "https://www.example.com/") is None


def test_extract_url_archive_absolute():
    archive = "https://web.archive.org/web/20191015120000/https://www.example.com/a.pdf"
    sel = make_selector(archive, "https://web.archive.org/")
    assert BuildDailyUrlsSpider.extract_url(sel, "https://web.archive.org/") == (
        "https://www.example.com/a.pdf",
        archive,
    )


def test_extract_url_archive_relative():
    sel = make_selector(
        "/web/20191015120000/https://www.example.com/a.pdf",
        "https://web.archive.org/",
    )
    assert BuildDailyUrlsSpider.extract_url(sel, "https://web.archive.org/") == (
        "https://www.example.com/a.pdf",
        "https://web.archive.org/web/20191015120000/https://www.example.com/a.pdf",
    )


# --- parse ---


def test_parse_yields_url_record_items():
    spider = BuildDailyUrlsSpider.__new__(BuildDailyUrlsSpider)
    items = list(spider.parse(make_response(["/a.pdf", "/b.pdf"])))
    assert len(items) == 2
    assert all(isinstance(i, UrlRecordItem) for i in items)
    assert items[0]["canonical_url"] == "https://www.example.com/a.pdf"
    assert items[0]["archive_url"] is None
    assert items[0]["state"] == "pending"


def test_parse_extracts_log_date_from_url():
    spider = BuildDailyUrlsSpider.__new__(BuildDailyUrlsSpider)
    items = list(spider.parse(make_response(["/DocumentCenter/View/22973/2026-05-01"])))
    assert len(items) == 1
    from datetime import date

    assert items[0]["log_date"] == date(2026, 5, 1)


def test_parse_log_date_none_when_not_in_url():
    spider = BuildDailyUrlsSpider.__new__(BuildDailyUrlsSpider)
    items = list(spider.parse(make_response(["/a.pdf"])))
    assert items[0]["log_date"] is None


def test_parse_archive_sets_both_url_fields():
    archive = "https://web.archive.org/web/20191015120000/https://www.example.com/a.pdf"
    items = list(
        BuildDailyUrlsSpider.__new__(BuildDailyUrlsSpider).parse(
            make_response([archive], base_url="https://web.archive.org/")
        )
    )
    assert len(items) == 1
    assert items[0]["canonical_url"] == "https://www.example.com/a.pdf"
    assert items[0]["archive_url"] == archive


def test_parse_skips_missing_href():
    spider = BuildDailyUrlsSpider.__new__(BuildDailyUrlsSpider)
    html = b'<html><body><a class="fileType pdf ">No href</a></body></html>'
    assert list(spider.parse(HtmlResponse(url="http://example.com", body=html))) == []


def test_parse_no_matches():
    assert (
        list(
            BuildDailyUrlsSpider.__new__(BuildDailyUrlsSpider).parse(make_response([]))
        )
        == []
    )
