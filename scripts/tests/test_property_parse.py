from pathlib import Path

import pytest

from scripts.models.property import PropertyRecord
from scripts.properties.parse import parse_parcel

# A real page from gis.vgsi.com. The parcel is owned by a business, and the earlier
# owners in its sales history are replaced with made-up names.
FIXTURE = Path(__file__).parent / "fixtures" / "vgsi" / "parcel_business.html"
PARCEL_HTML = FIXTURE.read_bytes()
PARCEL_URL = "https://gis.vgsi.com/LebanonNH/Parcel.aspx?pid=1949"

SECTIONS = {
    "land",
    "buildings",
    "outbuildings",
    "extra_features",
    "value_history",
    "sales",
}


@pytest.fixture
def record() -> PropertyRecord:
    return parse_parcel(PARCEL_HTML, PARCEL_URL)


def test_a_parcel_page_gives_every_value_converted(record):
    summary = record.model_dump(exclude=SECTIONS)

    assert summary == {
        "vgsi_pid": "1949",
        "mblu": "91/264///",
        "location": "1 MECHANIC ST",
        "owner": "ONE MECHANIC STREET LLC",
        "co_owner": None,
        "owner_address": "PO BOX 1325 LEBANON, NH 03766",
        "account_number": "2775",
        "use_code": "1120",
        "land_use": "APT 9+UP",
        "zone": "LD",
        "neighborhood": "C3",
        "lot_size_acres": 0.30,
        "year_built": 1900,
        "building_sqft": 6848,
        "assessed_land": 185700,
        "assessed_building": 100200,
        "assessed_total": 285900,
        "assessment_year": 2025,
        "appraised_land": 361500,
        "appraised_building": 1140700,
        "appraised_total": 1502200,
        "detail_url": PARCEL_URL,
    }
    assert record.land is not None
    assert record.land["Size (Acres)"] == "0.30"


def test_the_sections_below_the_summary_are_kept(record):
    assert record.buildings is not None
    [building] = record.buildings
    assert building["heading"] == "Building 1 : Section 1"
    assert building["attributes"]["Living Area"] == "6,848"
    assert building["construction"]["Style"] == "MULTI-GRDN"
    assert building["sub_areas"][0] == {
        "Code": "FFL",
        "Description": "1ST FLOOR",
        "Gross Area": "3,424",
        "Living Area": "3,424",
    }
    assert record.outbuildings is not None
    assert [row["Description"] for row in record.outbuildings] == ["PAVING", "GARAGE"]
    assert record.value_history is not None
    assert record.value_history["assessment"][0]["Total"] == "$285,900"
    assert record.value_history["appraisal"][0]["Total"] == "$1,517,300"


def test_the_sales_grid_gives_its_rows_newest_first(record):
    first = record.sales[0]
    assert (first.owner, first.sale_price, first.book_page, first.instrument) == (
        "ONE MECHANIC STREET LLC",
        264000,
        "4446/0736",
        "44",
    )
    assert first.certificate is None
    assert str(first.sale_date) == "2019-06-27"
    assert [sale.owner for sale in record.sales] == [
        "ONE MECHANIC STREET LLC",
        "EXAMPLE, PAT TTEE",
        "EXAMPLE, ROBIN",
        "EXAMPLE, ALEX",
    ]
