"""One VGSI parcel page to a PropertyRecord. Nothing here touches a network or a database."""

from typing import Any

from parsel import Selector

from scripts.models.property import PropertyRecord

# The page's label for each sales column, and the field it fills.
SALE_COLUMNS = {
    "Owner": "owner",
    "Sale Price": "sale_price",
    "Certificate": "certificate",
    "Book & Page": "book_page",
    "Instrument": "instrument",
    "Sale Date": "sale_date",
}


def parcel_id(url: str) -> str:
    return url.split("pid=")[-1].split("&")[0]


def parse_parcel(html: str | bytes, url: str) -> PropertyRecord:
    """Every value is read as the text the page printed, and PropertyRecord converts it."""
    text = html.decode("utf-8", errors="replace") if isinstance(html, bytes) else html
    page = Selector(text=text)
    assessment = next(iter(_grid(page, "grdCurrentValueAsmt")), {})
    appraisal = next(iter(_grid(page, "grdCurrentValueAppr")), {})
    buildings = _buildings(page)
    first_building = buildings[0]["attributes"] if buildings else {}
    sales = [
        {SALE_COLUMNS[column]: value for column, value in row.items()}
        for row in _grid(page, "grdSales")
        if row.keys() == SALE_COLUMNS.keys()
    ]
    return PropertyRecord.model_validate(
        {
            "vgsi_pid": parcel_id(url),
            "location": _label(page, "lblLocation"),
            "owner": _label(page, "lblOwner"),
            "co_owner": _label(page, "lblCoOwner"),
            "owner_address": _label(page, "lblAddr1"),
            "mblu": _label(page, "lblMblu"),
            "account_number": _label(page, "lblAcctNum"),
            "use_code": _label(page, "lblUseCode"),
            "land_use": _label(page, "lblUseCodeDescription"),
            "zone": _label(page, "lblZone"),
            "neighborhood": _label(page, "lblNbhd"),
            "lot_size_acres": _label(page, "lblLndSize"),
            "year_built": first_building.get("Year Built"),
            "building_sqft": first_building.get("Living Area"),
            "assessed_land": assessment.get("Land"),
            "assessed_building": assessment.get("Improvements"),
            "assessed_total": assessment.get("Total"),
            "assessment_year": assessment.get("Valuation Year"),
            "appraised_land": appraisal.get("Land"),
            "appraised_building": appraisal.get("Improvements"),
            "appraised_total": appraisal.get("Total"),
            "land": {**_pairs(page, "tblLandUse"), **_pairs(page, "tblLand")},
            "buildings": buildings,
            "outbuildings": _grid(page, "grdOb"),
            "extra_features": _grid(page, "grdXf"),
            "value_history": {
                "assessment": _grid(page, "grdHistoryValuesAsmt"),
                "appraisal": _grid(page, "grdHistoryValuesAppr"),
            },
            "detail_url": url,
            "sales": sales,
        }
    )


def _clean(node: Selector) -> str:
    return _squeeze(node.xpath(".//text()").getall())


def _squeeze(texts: list[str]) -> str:
    return " ".join(" ".join(texts).split())


def _label(page: Selector, name: str) -> str | None:
    return _squeeze(page.css(f"#MainContent_{name} ::text").getall()) or None


def _table(page: Selector, suffix: str) -> Selector | None:
    return next(iter(page.css(f"table[id$='{suffix}']")), None)


def _grid(page: Selector, suffix: str) -> list[dict[str, str]]:
    """A table with a header row, as one dict per data row."""
    table = _table(page, suffix)
    if table is None:
        return []
    headers = [_clean(th) for th in table.css("tr th")]
    cells = ([_clean(td) for td in row.css("td")] for row in table.css("tr"))
    return [
        dict(zip(headers, row, strict=True))
        for row in cells
        if len(row) == len(headers)
    ]


def _pairs(page: Selector, suffix: str) -> dict[str, str]:
    """A table of label and value rows, with each label's trailing colon dropped."""
    table = _table(page, suffix)
    if table is None:
        return {}
    rows = ([_clean(td) for td in row.css("td")] for row in table.css("tr"))
    return {row[0].rstrip(":"): row[1] for row in rows if len(row) == 2}


def _buildings(page: Selector) -> list[dict[str, Any]]:
    buildings = []
    for table in page.css("table[id$='_tblBldg']"):
        # Each section's ids share a prefix, such as MainContent_ctl02_.
        prefix = table.attrib["id"].removesuffix("tblBldg")
        buildings.append(
            {
                "heading": _squeeze(page.css(f"#{prefix}lblHeading ::text").getall()),
                "attributes": _pairs(page, f"{prefix}tblBldg"),
                "construction": _pairs(page, f"{prefix}grdCns"),
                "sub_areas": _grid(page, f"{prefix}grdSub"),
            }
        )
    return buildings
