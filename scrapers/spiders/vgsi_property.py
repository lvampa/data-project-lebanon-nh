import re
from urllib.parse import urljoin

import logfire
import scrapy
from items.property import PropertyItem
from scrapy.http import Request, Response

BASE_URL = "https://gis.vgsi.com/LebanonNH/"


def _parse_money(text: str | None) -> int | None:
    if not text:
        return None
    cleaned = re.sub(r"[^0-9]", "", text.strip())
    return int(cleaned) if cleaned else None


def _parse_float(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[^0-9.]", "", text.strip())
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_int(text: str | None) -> int | None:
    if not text:
        return None
    cleaned = re.sub(r"[^0-9]", "", text.strip())
    return int(cleaned) if cleaned else None


def _text(response: Response, suffix: str) -> str | None:
    val = response.css(f"[id$='{suffix}']::text").get()
    return val.strip() if val else None


class VgsiPropertySpider(scrapy.Spider):
    name = "vgsi_property"
    allowed_domains = ["gis.vgsi.com"]

    async def start(self):
        yield Request(urljoin(BASE_URL, "Streets.aspx"), callback=self.parse)

    def parse(self, response: Response, **kwargs):
        links = response.css("a[href*='Streets.aspx?Name=']")
        logfire.info("vgsi streets index", count=len(links))
        for link in links:
            yield Request(
                urljoin(BASE_URL, link.attrib["href"]),
                callback=self.parse_street,
            )

    def parse_street(self, response: Response, **kwargs):
        for link in response.css("a[href*='Parcel.aspx?pid=']"):
            yield Request(
                urljoin(BASE_URL, link.attrib["href"]),
                callback=self.parse_parcel,
            )

    def parse_parcel(self, response: Response, **kwargs):
        pid = response.url.split("pid=")[-1].split("&")[0]

        sales = []
        for row in response.css("[id$='grdSales'] tbody tr"):
            cells = [td.css("::text").get("").strip() for td in row.css("td")]
            if len(cells) >= 4:
                sales.append(
                    {
                        "sale_date": cells[0] or None,
                        "sale_price": _parse_money(cells[1]),
                        "grantee": cells[2] or None,  # buyer
                        "grantor": cells[3] or None,  # seller
                    }
                )

        item = PropertyItem(
            parcel_id=pid,
            location=_text(response, "lblLocation"),
            owner=_text(response, "lblOwner"),
            owner_address=_text(response, "lblMailingAddress"),
            land_use=_text(response, "lblPropClass"),
            assessed_land=_parse_money(_text(response, "lblLndVal")),
            assessed_building=_parse_money(_text(response, "lblBldVal")),
            assessed_total=_parse_money(_text(response, "lblApprValue")),
            lot_size_acres=_parse_float(_text(response, "lblLotSize")),
            year_built=_parse_int(_text(response, "lblYearBuilt")),
            building_sqft=_parse_int(_text(response, "lblLivingArea")),
            assessment_year=_parse_int(_text(response, "lblYear")),
            detail_url=response.url,
            sales=sales,
        )
        logfire.info("vgsi parcel scraped", pid=pid, sales=len(sales))
        yield item
