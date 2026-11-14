import asyncio
import gzip
import socket
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from mongo.archive import RawArchive, archive_collection
from mongo.client import MongoDB
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from scripts.scrape.scrape_llcs import (
    CLAIM_LEASE,
    parse_llc_detail,
    release_stale_claims,
    save_lookup,
    scrape_llc,
)

NOW = datetime(2026, 10, 31, 12, 0, 0)


def compiled(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


def executed_values(session: MagicMock) -> dict:
    statement = session.execute.call_args.args[0]
    return {col.name: value.value for col, value in statement._values.items()}


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


# --- stale claims ---


def test_claim_lease_is_two_hours():
    assert CLAIM_LEASE.total_seconds() == 2 * 60 * 60


def test_release_stale_claims_resets_old_in_progress_rows_to_pending():
    sql = compiled(release_stale_claims(NOW))
    assert sql.startswith("UPDATE llcs SET lookup_status='pending'")
    assert "llcs.lookup_status = 'in_progress'" in sql
    assert "llcs.last_looked_up_at < '2026-10-31 10:00:00'" in sql


def test_release_stale_claims_includes_claims_with_no_timestamp():
    sql = compiled(release_stale_claims(NOW))
    assert "llcs.last_looked_up_at IS NULL" in sql


# --- save_lookup ---


def test_save_lookup_marks_complete_with_validated_fields():
    session = MagicMock()
    data = parse_llc_detail(DETAIL_HTML, business_id="775794")
    save_lookup(session, llc_id=7, data=data, now=NOW)
    values = executed_values(session)
    assert values["lookup_status"] == "complete"
    assert values["nh_business_id"] == "775794"
    assert values["principals"][0]["name"] == "dick anagnost"
    session.commit.assert_called_once()


def test_save_lookup_marks_not_found_as_error():
    session = MagicMock()
    save_lookup(session, llc_id=7, data=None, now=NOW)
    values = executed_values(session)
    assert values["lookup_status"] == "error"
    assert values["error_message"] == "Not found on NH SOS"


def test_save_lookup_rejects_invalid_data_before_writing():
    session = MagicMock()
    with pytest.raises(ValidationError):
        save_lookup(session, llc_id=7, data={"formation_date": "N/A"}, now=NOW)
    session.execute.assert_not_called()


# --- scrape_llc: the raw archive ---


class FakeLink:
    def __init__(self, page: "FakePage", href: str | None) -> None:
        self._page = page
        self._href = href

    @property
    def first(self) -> "FakeLink":
        return self

    async def count(self) -> int:
        return 1

    async def get_attribute(self, name: str) -> str | None:
        return self._href

    async def click(self) -> None:
        self._page.url = self._page.detail_url


class FakePage:
    """The Playwright calls scrape_llc makes, for one search with one result."""

    def __init__(self, href: str | None, detail_url: str) -> None:
        self.url = ""
        self.detail_url = detail_url
        self._href = href

    async def goto(self, url: str) -> None:
        self.url = url

    async def fill(self, selector: str, value: str) -> None:
        pass

    async def click(self, selector: str) -> None:
        pass

    async def wait_for_load_state(self, state: str) -> None:
        pass

    def locator(self, selector: str) -> FakeLink:
        return FakeLink(self, self._href)

    async def content(self) -> str:
        return DETAIL_HTML


DETAIL_URL = (
    "https://quickstart.sos.nh.gov/online/BusinessInquire/"
    "BusinessInformation?businessID=757045"
)


def test_the_business_page_is_archived_under_its_business_id(raw_sources):
    archive = RawArchive(raw_sources)
    page = FakePage(href="BusinessInformation?businessID=757045", detail_url=DETAIL_URL)

    business_id, data = asyncio.run(scrape_llc(page, "ANAGNOST LLC", archive))
    archive.flush()

    [version] = list(raw_sources.find({"source": "nh_sos_business"}))
    assert version["source_key"] == "757045" == business_id
    assert version["url"] == DETAIL_URL
    assert gzip.decompress(version["body_gzip"]).decode() == DETAIL_HTML
    assert version["spider"] == "scrape_llcs"
    assert data is not None and data["business_status"] == "Good Standing"


def test_a_page_with_no_business_id_is_keyed_by_the_searched_name(raw_sources):
    archive = RawArchive(raw_sources)
    page = FakePage(href=None, detail_url="https://quickstart.sos.nh.gov/x")

    asyncio.run(scrape_llc(page, "ANAGNOST LLC", archive))
    archive.flush()

    [version] = list(raw_sources.find({"source": "nh_sos_business"}))
    assert version["source_key"] == "ANAGNOST LLC"


def closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_the_lookup_is_unchanged_when_mongodb_is_unreachable(monkeypatch):
    monkeypatch.setenv("MONGO_HOST", "127.0.0.1")
    monkeypatch.setenv("MONGO_PORT", str(closed_port()))
    archive = RawArchive(archive_collection(MongoDB()))
    page = FakePage(href="BusinessInformation?businessID=757045", detail_url=DETAIL_URL)

    business_id, data = asyncio.run(scrape_llc(page, "ANAGNOST LLC", archive))
    counts = archive.flush()

    assert business_id == "757045"
    assert data == parse_llc_detail(DETAIL_HTML, "757045")
    assert counts.failed == 1
