from urllib.parse import urljoin

import logfire
import scrapy
from items.property import PropertyItem
from scrapy.http import Request, Response
from scrapy.selector import Selector

BASE_URL = "https://gis.vgsi.com/LebanonNH/"
# Streets.aspx lists the A streets, so the link to letter A would fetch the same page.
FIRST_LETTER_HREF = "Streets.aspx?Letter=A"
# The page's label for each sales column, and the field it fills.
SALE_COLUMNS = {
    "Owner": "owner",
    "Sale Price": "sale_price",
    "Certificate": "certificate",
    "Book & Page": "book_page",
    "Instrument": "instrument",
    "Sale Date": "sale_date",
}


def _clean(node: Selector) -> str:
    return _squeeze(node.xpath(".//text()").getall())


def _squeeze(texts: list[str]) -> str:
    return " ".join(" ".join(texts).split())


def _label(response: Response, name: str) -> str | None:
    return _squeeze(response.css(f"#MainContent_{name} ::text").getall()) or None


def _table(scope: Response | Selector, suffix: str) -> Selector | None:
    return next(iter(scope.css(f"table[id$='{suffix}']")), None)


def _grid(scope: Response | Selector, suffix: str) -> list[dict[str, str]]:
    """A table with a header row, as one dict per data row."""
    table = _table(scope, suffix)
    if table is None:
        return []
    headers = [_clean(th) for th in table.css("tr th")]
    cells = ([_clean(td) for td in row.css("td")] for row in table.css("tr"))
    return [
        dict(zip(headers, row, strict=True))
        for row in cells
        if len(row) == len(headers)
    ]


def _pairs(scope: Response | Selector, suffix: str) -> dict[str, str]:
    """A table of label and value rows, with each label's trailing colon dropped."""
    table = _table(scope, suffix)
    if table is None:
        return {}
    rows = ([_clean(td) for td in row.css("td")] for row in table.css("tr"))
    return {row[0].rstrip(":"): row[1] for row in rows if len(row) == 2}


def _buildings(response: Response) -> list[dict]:
    buildings = []
    for table in response.css("table[id$='_tblBldg']"):
        # Each section's ids share a prefix, such as MainContent_ctl02_.
        prefix = table.attrib["id"].removesuffix("tblBldg")
        buildings.append(
            {
                "heading": _squeeze(
                    response.css(f"#{prefix}lblHeading ::text").getall()
                ),
                "attributes": _pairs(response, f"{prefix}tblBldg"),
                "construction": _pairs(response, f"{prefix}grdCns"),
                "sub_areas": _grid(response, f"{prefix}grdSub"),
            }
        )
    return buildings


def _parcel_id(url: str) -> str:
    return url.split("pid=")[-1].split("&")[0]


class VgsiPropertySpider(scrapy.Spider):
    name = "vgsi_property"
    allowed_domains = ["gis.vgsi.com"]
    archive_source = "vgsi_parcel"

    def archive_key(self, response: Response) -> str | None:
        # Street index pages only list parcels; the parcel pages are the originals.
        if "Parcel.aspx" not in response.url:
            return None
        return _parcel_id(response.url)

    async def start(self):
        yield Request(urljoin(BASE_URL, "Streets.aspx"), callback=self.parse)

    def parse(self, response: Response, **kwargs):
        # An index page lists one letter's streets and links to the other letters.
        # The dupe filter stops the letters from following each other round.
        links = response.css("a[href*='Streets.aspx?Name=']")
        logfire.info("vgsi streets index", count=len(links))
        for link in links:
            yield Request(
                urljoin(BASE_URL, link.attrib["href"]),
                callback=self.parse_street,
            )
        for link in response.css("a[href*='Streets.aspx?Letter=']"):
            if link.attrib["href"] != FIRST_LETTER_HREF:
                yield Request(
                    urljoin(BASE_URL, link.attrib["href"]), callback=self.parse
                )

    def parse_street(self, response: Response, **kwargs):
        for link in response.css("a[href*='Parcel.aspx?pid=']"):
            yield Request(
                urljoin(BASE_URL, link.attrib["href"]),
                callback=self.parse_parcel,
            )

    def parse_parcel(self, response: Response, **kwargs):
        pid = _parcel_id(response.url)
        assessment = next(iter(_grid(response, "grdCurrentValueAsmt")), {})
        appraisal = next(iter(_grid(response, "grdCurrentValueAppr")), {})
        buildings = _buildings(response)
        first_building = buildings[0]["attributes"] if buildings else {}
        sales = [
            {SALE_COLUMNS[column]: value for column, value in row.items()}
            for row in _grid(response, "grdSales")
            if row.keys() == SALE_COLUMNS.keys()
        ]

        # Plain strings only. PropertyRecord turns them into numbers and dates.
        item = PropertyItem(
            parcel_id=pid,
            location=_label(response, "lblLocation"),
            owner=_label(response, "lblOwner"),
            co_owner=_label(response, "lblCoOwner"),
            owner_address=_label(response, "lblAddr1"),
            mblu=_label(response, "lblMblu"),
            account_number=_label(response, "lblAcctNum"),
            use_code=_label(response, "lblUseCode"),
            land_use=_label(response, "lblUseCodeDescription"),
            zone=_label(response, "lblZone"),
            neighborhood=_label(response, "lblNbhd"),
            lot_size_acres=_label(response, "lblLndSize"),
            year_built=first_building.get("Year Built"),
            building_sqft=first_building.get("Living Area"),
            assessed_land=assessment.get("Land"),
            assessed_building=assessment.get("Improvements"),
            assessed_total=assessment.get("Total"),
            assessment_year=assessment.get("Valuation Year"),
            appraised_land=appraisal.get("Land"),
            appraised_building=appraisal.get("Improvements"),
            appraised_total=appraisal.get("Total"),
            land={**_pairs(response, "tblLandUse"), **_pairs(response, "tblLand")},
            buildings=buildings,
            outbuildings=_grid(response, "grdOb"),
            extra_features=_grid(response, "grdXf"),
            value_history={
                "assessment": _grid(response, "grdHistoryValuesAsmt"),
                "appraisal": _grid(response, "grdHistoryValuesAppr"),
            },
            detail_url=response.url,
            sales=sales,
        )
        logfire.info("vgsi parcel scraped", pid=pid, sales=len(sales))
        yield item
