import pytest
from scrapy.http import HtmlResponse

from items.city_staff import CityStaffItem
from spiders.city_staff import CityStaffSpider, DIRECTORY_SOURCES

ROSTER_HTML = b"""
<html><body>
<h2>Patrol Division</h2>
<dl>
  <dt><img alt="Jane Doe"/></dt>
  <dd><h4>Jane Doe</h4><p>Patrol Officer</p><p>jdoe@police.nh.gov</p><p>(603) 448-1234</p></dd>
</dl>
<dl>
  <dt><img alt="John Smith"/></dt>
  <dd><h4>John Smith</h4><p>Sergeant</p></dd>
</dl>
</body></html>
"""

DIRECTORY_HTML = b"""
<html><body>
<table>
  <thead><tr><th>Name</th><th>Title</th><th>Email</th><th>Phone</th></tr></thead>
  <tbody>
    <tr>
      <td>Mary Johnson</td>
      <td>City Clerk</td>
      <td>mjohnson@lebanonnh.gov</td>
      <td>(603) 448-3054</td>
    </tr>
    <tr>
      <td>Bob Williams</td>
      <td>Deputy Clerk</td>
      <td></td>
      <td>(603) 448-3055</td>
    </tr>
  </tbody>
</table>
</body></html>
"""

COUNCIL_INDEX_HTML = b"""
<html><body>
<div id="main-content">
  <a href="/1946/Councilor-Kellen-Appleton">Councilor Kellen Appleton</a>
  <a href="/1855/Councilor-Nicole-Ford-Burley">Councilor Nicole Ford Burley</a>
  <a href="/337/City-Council">Back</a>
</div>
</body></html>
"""

COUNCILOR_HTML = b"""
<html><head><title>Councilor Kellen Appleton | Lebanon, NH</title></head>
<body>
<div id="main-content">
  <h1>Councilor Kellen Appleton</h1>
  <p>Councilor, At-Large (Term Expires 3/28)</p>
  <a href="mailto:Kellen.Appleton@lebanonnh.gov">Email Councilor Appleton</a>
</div>
</body></html>
"""


@pytest.fixture
def spider():
    return CityStaffSpider()


def test_parse_roster_yields_items(spider):
    response = HtmlResponse(
        url="https://www.lebanonnh.gov/796/Department-Roster",
        body=ROSTER_HTML,
    )
    results = list(spider.parse_dept_roster(response, department="Police"))
    assert len(results) == 2
    assert all(isinstance(r, CityStaffItem) for r in results)


def test_parse_roster_extracts_fields(spider):
    response = HtmlResponse(
        url="https://www.lebanonnh.gov/796/Department-Roster",
        body=ROSTER_HTML,
    )
    items = list(spider.parse_dept_roster(response, department="Police"))
    jane = items[0]
    assert jane["name"] == "Jane Doe"
    assert jane["title"] == "Patrol Officer"
    assert jane["department"] == "Police"
    assert jane["division"] == "Patrol Division"
    assert jane["email"] == "jdoe@police.nh.gov"
    assert jane["phone"] == "(603) 448-1234"


def test_parse_roster_missing_contact(spider):
    """Staff with no email/phone get None, not empty string."""
    response = HtmlResponse(
        url="https://www.lebanonnh.gov/1718/Department-Roster",
        body=ROSTER_HTML,
    )
    items = list(spider.parse_dept_roster(response, department="Fire"))
    smith = items[1]
    assert smith["name"] == "John Smith"
    assert smith["email"] is None
    assert smith["phone"] is None


def test_parse_directory_table_yields_items(spider):
    response = HtmlResponse(
        url="https://www.lebanonnh.gov/Directory.aspx?did=37",
        body=DIRECTORY_HTML,
    )
    results = list(spider.parse_directory_table(response, department="Clerk"))
    assert len(results) == 2
    assert all(isinstance(r, CityStaffItem) for r in results)


def test_parse_directory_table_extracts_fields(spider):
    response = HtmlResponse(
        url="https://www.lebanonnh.gov/Directory.aspx?did=37",
        body=DIRECTORY_HTML,
    )
    items = list(spider.parse_directory_table(response, department="Clerk"))
    mary = items[0]
    assert mary["name"] == "Mary Johnson"
    assert mary["title"] == "City Clerk"
    assert mary["department"] == "Clerk"
    assert mary["email"] == "mjohnson@lebanonnh.gov"
    assert mary["phone"] == "(603) 448-3054"


def test_parse_directory_table_empty_email_is_none(spider):
    response = HtmlResponse(
        url="https://www.lebanonnh.gov/Directory.aspx?did=37",
        body=DIRECTORY_HTML,
    )
    items = list(spider.parse_directory_table(response, department="Clerk"))
    bob = items[1]
    assert bob["email"] is None


def test_parse_council_index_yields_member_requests(spider):
    response = HtmlResponse(
        url="https://www.lebanonnh.gov/337/City-Council",
        body=COUNCIL_INDEX_HTML,
    )
    results = list(spider.parse_council_index(response))
    # Should follow the two councilor links, not the "Back" link
    assert len(results) == 2
    assert all("Councilor" in r.url for r in results)


def test_airport_directory_in_sources(spider):
    urls = [url for url, _ in DIRECTORY_SOURCES if "flyleb.com" in url]
    assert len(urls) == 1
    assert "flyleb.com" in spider.allowed_domains


def test_parse_directory_table_airport_department(spider):
    response = HtmlResponse(
        url="https://flyleb.com/directory.aspx?did=6",
        body=DIRECTORY_HTML,
    )
    items = list(spider.parse_directory_table(response, department="Airport"))
    assert len(items) == 2
    assert all(item["department"] == "Airport" for item in items)


def test_parse_council_member_extracts_fields(spider):
    response = HtmlResponse(
        url="https://www.lebanonnh.gov/1946/Councilor-Kellen-Appleton",
        body=COUNCILOR_HTML,
    )
    items = list(spider.parse_council_member(response))
    assert len(items) == 1
    item = items[0]
    assert item["name"] == "Kellen Appleton"
    assert item["department"] == "City Council"
    assert item["email"] == "Kellen.Appleton@lebanonnh.gov"
