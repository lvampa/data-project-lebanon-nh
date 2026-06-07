import pytest
from items.property import PropertyItem
from scrapy.http import HtmlResponse
from spiders.vgsi_property import VgsiPropertySpider

STREETS_INDEX_HTML = b"""
<html><body>
<table class="table">
  <tbody>
    <tr><td><a href="Streets.aspx?Name=ABBOTT+ST">ABBOTT ST</a></td></tr>
    <tr><td><a href="Streets.aspx?Name=ALLEN+ST">ALLEN ST</a></td></tr>
  </tbody>
</table>
</body></html>
"""

STREET_LIST_HTML = b"""
<html><body>
<table class="table">
  <tbody>
    <tr>
      <td><a href="Parcel.aspx?pid=10001">123 ABBOTT ST</a></td>
      <td>SMITH, JOHN</td>
    </tr>
    <tr>
      <td><a href="Parcel.aspx?pid=10002">125 ABBOTT ST</a></td>
      <td>DOE, JANE</td>
    </tr>
  </tbody>
</table>
</body></html>
"""

PARCEL_HTML = b"""
<html><body>
<span id="MainContent_lblLocation">123 ABBOTT ST</span>
<span id="MainContent_lblOwner">SMITH, JOHN</span>
<span id="MainContent_lblMailingAddress">PO BOX 1, LEBANON NH 03766</span>
<span id="MainContent_lblPropClass">101 - Res 1 Family</span>
<span id="MainContent_lblLndVal">$100,000</span>
<span id="MainContent_lblBldVal">$250,000</span>
<span id="MainContent_lblApprValue">$350,000</span>
<span id="MainContent_lblLotSize">0.25</span>
<span id="MainContent_lblYearBuilt">1985</span>
<span id="MainContent_lblLivingArea">1,450</span>
<table id="MainContent_grdSales">
  <thead><tr><th>Date</th><th>Price</th><th>Buyer</th><th>Seller</th></tr></thead>
  <tbody>
    <tr>
      <td>01/15/2019</td>
      <td>$320,000</td>
      <td>SMITH, JOHN</td>
      <td>JONES, BOB</td>
    </tr>
  </tbody>
</table>
</body></html>
"""


@pytest.fixture
def spider():
    return VgsiPropertySpider()


def test_parse_streets_index_yields_street_requests(spider):
    response = HtmlResponse(
        url="https://gis.vgsi.com/LebanonNH/Streets.aspx",
        body=STREETS_INDEX_HTML,
    )
    results = list(spider.parse(response))
    assert len(results) == 2
    urls = [r.url for r in results]
    assert any("ABBOTT" in u for u in urls)
    assert any("ALLEN" in u for u in urls)


def test_parse_street_list_yields_parcel_requests(spider):
    response = HtmlResponse(
        url="https://gis.vgsi.com/LebanonNH/Streets.aspx?Name=ABBOTT+ST",
        body=STREET_LIST_HTML,
    )
    results = list(spider.parse_street(response))
    assert len(results) == 2
    assert all("Parcel.aspx" in r.url for r in results)


def test_parse_parcel_yields_property_item(spider):
    response = HtmlResponse(
        url="https://gis.vgsi.com/LebanonNH/Parcel.aspx?pid=10001",
        body=PARCEL_HTML,
    )
    results = list(spider.parse_parcel(response))
    assert len(results) == 1
    item = results[0]
    assert isinstance(item, PropertyItem)
    assert item["parcel_id"] == "10001"
    assert item["location"] == "123 ABBOTT ST"
    assert item["owner"] == "SMITH, JOHN"
    assert item["owner_address"] == "PO BOX 1, LEBANON NH 03766"
    assert item["land_use"] == "101 - Res 1 Family"
    assert item["assessed_land"] == 100000
    assert item["assessed_building"] == 250000
    assert item["assessed_total"] == 350000
    assert item["lot_size_acres"] == pytest.approx(0.25)
    assert item["year_built"] == 1985
    assert item["building_sqft"] == 1450
    assert item["detail_url"] == "https://gis.vgsi.com/LebanonNH/Parcel.aspx?pid=10001"


def test_parse_parcel_extracts_sales(spider):
    response = HtmlResponse(
        url="https://gis.vgsi.com/LebanonNH/Parcel.aspx?pid=10001",
        body=PARCEL_HTML,
    )
    item = list(spider.parse_parcel(response))[0]
    assert len(item["sales"]) == 1
    sale = item["sales"][0]
    assert sale["sale_date"] == "01/15/2019"
    assert sale["sale_price"] == 320000
    assert sale["grantee"] == "SMITH, JOHN"  # buyer
    assert sale["grantor"] == "JONES, BOB"  # seller
