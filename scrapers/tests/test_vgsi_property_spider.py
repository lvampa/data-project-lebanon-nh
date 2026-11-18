from pathlib import Path

import pytest
from items.property import PropertyItem
from scrapy.http import HtmlResponse
from spiders.vgsi_property import VgsiPropertySpider

FIXTURES = Path(__file__).parent / "fixtures" / "vgsi"
# Real pages from gis.vgsi.com. The parcel is owned by a business, and the earlier
# owners in its sales history are replaced with made-up names.
PARCEL_HTML = (FIXTURES / "parcel_business.html").read_bytes()
STREETS_INDEX_HTML = (FIXTURES / "streets_index.html").read_bytes()
PARCEL_URL = "https://gis.vgsi.com/LebanonNH/Parcel.aspx?pid=1949"
# The fields that hold a table, and are checked on their own.
SECTIONS = {
    "land",
    "buildings",
    "outbuildings",
    "extra_features",
    "value_history",
    "sales",
}

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


@pytest.fixture
def item(spider) -> PropertyItem:
    response = HtmlResponse(url=PARCEL_URL, body=PARCEL_HTML)
    [item] = spider.parse_parcel(response)
    return item


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


def test_a_parcel_page_gives_every_value_as_text(item):
    summary = {key: value for key, value in item.items() if key not in SECTIONS}
    assert summary == {
        "parcel_id": "1949",
        "location": "1 MECHANIC ST",
        "owner": "ONE MECHANIC STREET LLC",
        "co_owner": None,
        "owner_address": "PO BOX 1325 LEBANON, NH 03766",
        "mblu": "91/ 264/ / /",
        "account_number": "2775",
        "use_code": "1120",
        "land_use": "APT 9+UP",
        "zone": "LD",
        "neighborhood": "C3",
        "lot_size_acres": "0.30",
        "year_built": "1900",
        "building_sqft": "6,848",
        "assessed_land": "$185,700",
        "assessed_building": "$100,200",
        "assessed_total": "$285,900",
        "assessment_year": "2025",
        "appraised_land": "$361,500",
        "appraised_building": "$1,140,700",
        "appraised_total": "$1,502,200",
        "detail_url": PARCEL_URL,
    }
    assert item["land"]["Size (Acres)"] == "0.30"
    assert item["land"]["Zone"] == "LD"


def test_the_sections_below_the_summary_are_kept(item):
    [building] = item["buildings"]
    assert building["heading"] == "Building 1 : Section 1"
    assert building["attributes"]["Living Area"] == "6,848"
    assert building["construction"]["Style"] == "MULTI-GRDN"
    assert building["sub_areas"][0] == {
        "Code": "FFL",
        "Description": "1ST FLOOR",
        "Gross Area": "3,424",
        "Living Area": "3,424",
    }
    assert [row["Description"] for row in item["outbuildings"]] == ["PAVING", "GARAGE"]
    history = item["value_history"]
    assert history["assessment"][0] == {
        "Valuation Year": "2025",
        "Improvements": "$100,200",
        "Land": "$185,700",
        "Total": "$285,900",
    }
    assert history["appraisal"][0]["Total"] == "$1,517,300"


def test_the_sales_grid_gives_its_rows_newest_first(item):
    assert item["sales"][0] == {
        "owner": "ONE MECHANIC STREET LLC",
        "sale_price": "$264,000",
        "certificate": "",
        "book_page": "4446/0736",
        "instrument": "44",
        "sale_date": "06/27/2019",
    }
    assert [sale["owner"] for sale in item["sales"]] == [
        "ONE MECHANIC STREET LLC",
        "EXAMPLE, PAT TTEE",
        "EXAMPLE, ROBIN",
        "EXAMPLE, ALEX",
    ]
