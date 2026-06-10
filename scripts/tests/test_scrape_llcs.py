import pytest
from scripts.scrape.scrape_llcs import parse_llc_detail

# Minimal fixture matching real NH SOS detail page structure
DETAIL_HTML = """
<html><body>
<table>
  <tr><td>Business Status:</td><td>Good Standing</td></tr>
  <tr><td>Business Creation Date:</td><td>07/28/2017</td></tr>
  <tr><td>Business Email:</td><td>dick@anagnost.com</td></tr>
  <tr><td>Phone #:</td><td>603-669-6194</td></tr>
</table>
<table id="principals">
  <thead><tr><th>Name/Title</th><th>Business Address</th></tr></thead>
  <tbody>
    <tr>
      <td>dick anagnost / Manager</td>
      <td>1662 elm st, Manchester, NH, 03101, USA</td>
    </tr>
  </tbody>
</table>
<div id="registered-agent">
  <p>Name: Kenneth A. Viscarello Esq.</p>
  <p>Registered Office Address: Sheehan Phinney Bass &amp; Green, 1000 Elm Street, Manchester, NH, 03101, USA</p>
</div>
</body></html>
"""


def test_parses_business_status():
    result = parse_llc_detail(DETAIL_HTML, business_id="775794")
    assert result["business_status"] == "Good Standing"


def test_parses_formation_date():
    from datetime import date
    result = parse_llc_detail(DETAIL_HTML, business_id="775794")
    assert result["formation_date"] == date(2017, 7, 28)


def test_parses_contact_info():
    result = parse_llc_detail(DETAIL_HTML, business_id="775794")
    assert result["business_email"] == "dick@anagnost.com"
    assert result["phone"] == "603-669-6194"


def test_parses_principals():
    result = parse_llc_detail(DETAIL_HTML, business_id="775794")
    assert len(result["principals"]) == 1
    assert result["principals"][0]["name"] == "dick anagnost"
    assert result["principals"][0]["title"] == "Manager"


def test_passes_through_business_id():
    result = parse_llc_detail(DETAIL_HTML, business_id="775794")
    assert result["nh_business_id"] == "775794"


def test_returns_none_formation_date_on_bad_format():
    html = DETAIL_HTML.replace("07/28/2017", "N/A")
    result = parse_llc_detail(html, business_id="775794")
    assert result["formation_date"] is None
