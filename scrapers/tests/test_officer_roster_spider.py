import pytest
from items.officer import OfficerItem
from scrapy.http import HtmlResponse
from spiders.officer_roster import OfficerRosterSpider

ROSTER_INDEX_HTML = b"""
<html><body>
<nav class="siteNav secondaryNav">
  <ul>
    <li><a href="/290/Patrol-Division">Patrol Division</a></li>
    <li><a href="/291/Investigations">Investigations</a></li>
  </ul>
</nav>
</body></html>
"""

DIVISION_HTML = b"""
<html><body>
<div id="main-content">
  <h1>Patrol Division</h1>
  <table>
    <tbody>
      <tr>
        <td>Chief</td>
        <td>John Smith</td>
        <td>(603) 448-1212</td>
        <td>jsmith@lebanonnh.gov</td>
      </tr>
      <tr>
        <td>Sergeant</td>
        <td>Jane Doe</td>
        <td>(603) 448-1213</td>
        <td>jdoe@lebanonnh.gov</td>
      </tr>
    </tbody>
  </table>
</div>
</body></html>
"""


@pytest.fixture
def spider():
    return OfficerRosterSpider()


def test_parse_index_yields_division_requests(spider):
    response = HtmlResponse(
        url="https://www.lebanonnh.gov/287/Divisions-Roster",
        body=ROSTER_INDEX_HTML,
    )
    results = list(spider.parse(response))
    urls = [r.url for r in results]
    assert any("290" in u or "Patrol" in u for u in urls)
    assert any("291" in u or "Investigations" in u for u in urls)


def test_parse_division_yields_officer_items(spider):
    response = HtmlResponse(
        url="https://www.lebanonnh.gov/290/Patrol-Division",
        body=DIVISION_HTML,
    )
    results = list(spider.parse_division(response, division="Patrol Division"))
    assert len(results) == 2
    assert all(isinstance(r, OfficerItem) for r in results)


def test_parse_division_extracts_fields(spider):
    response = HtmlResponse(
        url="https://www.lebanonnh.gov/290/Patrol-Division",
        body=DIVISION_HTML,
    )
    items = list(spider.parse_division(response, division="Patrol Division"))
    chief = items[0]
    assert chief["name"] == "John Smith"
    assert chief["rank"] == "Chief"
    assert chief["division"] == "Patrol Division"
    assert chief["phone"] == "(603) 448-1212"
    assert chief["email"] == "jsmith@lebanonnh.gov"
    assert chief["source_url"] == "https://www.lebanonnh.gov/290/Patrol-Division"
