from datetime import datetime
from pathlib import Path

import pytest
from crawl_runs import finish_run, start_run
from postgres.models.crawl_run import CrawlRun
from scrapy.http import HtmlResponse
from spiders.vgsi_property import VgsiPropertySpider

# A real page from gis.vgsi.com. It holds only links.
STREETS_INDEX_HTML = (
    Path(__file__).parent / "fixtures" / "vgsi" / "streets_index.html"
).read_bytes()

STREET_LIST_HTML = b"""
<html><body>
<ul>
  <li><a href='Parcel.aspx?pid=10001'>123 ABBOTT ST</a>&nbsp; Mblu: 1/ 2/ / /</li>
  <li><a href='Parcel.aspx?pid=10002'>125 ABBOTT ST</a>&nbsp; Mblu: 1/ 3/ / /</li>
</ul>
</body></html>
"""


@pytest.fixture
def spider():
    return VgsiPropertySpider()


def test_the_index_page_leads_to_every_street_and_every_letter_but_a(spider):
    response = HtmlResponse(
        url="https://gis.vgsi.com/LebanonNH/Streets.aspx", body=STREETS_INDEX_HTML
    )

    requests = list(spider.parse(response))

    streets = [r for r in requests if r.callback == spider.parse_street]
    letters = [r for r in requests if r.callback == spider.parse]
    assert len(streets) == 36
    assert [r.url.split("Letter=")[-1] for r in letters] == list(
        "BCDEFGHIJKLMNOPQRSTUVWY"
    )


def test_parse_follows_every_letter_but_a(spider):
    response = HtmlResponse(
        url="https://gis.vgsi.com/LebanonNH/Streets.aspx",
        body=b"""
        <a href='Streets.aspx?Letter=A'>A</a>
        <a href='Streets.aspx?Letter=B'>B</a>
        <a href='Streets.aspx?Letter=Y'>Y</a>
        <a href='Streets.aspx?Name=ABBOTT'>ABBOTT</a>
        """,
    )

    requests = list(spider.parse(response))

    assert [(r.url, r.callback) for r in requests] == [
        (
            "https://gis.vgsi.com/LebanonNH/Streets.aspx?Name=ABBOTT",
            spider.parse_street,
        ),
        ("https://gis.vgsi.com/LebanonNH/Streets.aspx?Letter=B", spider.parse),
        ("https://gis.vgsi.com/LebanonNH/Streets.aspx?Letter=Y", spider.parse),
    ]


def test_a_street_page_leads_to_its_parcels(spider):
    response = HtmlResponse(
        url="https://gis.vgsi.com/LebanonNH/Streets.aspx?Name=ABBOTT",
        body=STREET_LIST_HTML,
    )

    requests = list(spider.parse_street(response))

    assert [r.url for r in requests] == [
        "https://gis.vgsi.com/LebanonNH/Parcel.aspx?pid=10001",
        "https://gis.vgsi.com/LebanonNH/Parcel.aspx?pid=10002",
    ]


def test_a_parcel_page_yields_nothing_and_is_counted(spider):
    response = HtmlResponse(
        url="https://gis.vgsi.com/LebanonNH/Parcel.aspx?pid=10001", body=b"<html/>"
    )

    assert spider.parse_parcel(response) is None
    assert spider.pages == 1


def test_a_finished_crawl_records_its_run(db_session, spider):
    spider.run_id = start_run(spider.name)
    spider.pages = 3

    spider.close_run("finished")

    run = db_session.get(CrawlRun, spider.run_id)
    assert run is not None
    assert (run.source, run.pages) == ("vgsi_property", 3)
    assert isinstance(run.finished_at, datetime)


def test_a_stopped_crawl_stays_unfinished(db_session, spider):
    spider.run_id = start_run(spider.name)

    spider.close_run("shutdown")

    run = db_session.get(CrawlRun, spider.run_id)
    assert run is not None
    assert run.finished_at is None


def test_finish_run_stamps_the_pages(db_session):
    run_id = start_run("vgsi_property")

    finish_run(run_id, 7)

    run = db_session.get(CrawlRun, run_id)
    assert run is not None
    assert run.pages == 7
