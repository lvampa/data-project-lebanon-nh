import pytest
from datetime import date
from pydantic import ValidationError
from models.property import PropertyRecord, SaleRecord


def make_property(**kwargs):
    defaults = dict(
        parcel_id="10001",
        location="  123 MAIN ST  ",
        owner="SMITH, JOHN",
        owner_address="PO BOX 1, LEBANON NH 03766",
        land_use="101 - Res 1 Family",
        lot_size_acres=0.25,
        year_built=1985,
        building_sqft=1450,
        assessed_land=100000,
        assessed_building=250000,
        assessed_total=350000,
        assessment_year=2025,
        detail_url="https://gis.vgsi.com/LebanonNH/Parcel.aspx?Pid=10001",
        sales=[],
    )
    return {**defaults, **kwargs}


def test_property_record_shape():
    record = PropertyRecord.model_validate(make_property())
    assert record.parcel_id == "10001"
    assert record.assessed_total == 350000
    assert record.sales == []


def test_property_record_strips_whitespace():
    record = PropertyRecord.model_validate(make_property(location="  123 MAIN ST  "))
    assert record.location == "123 MAIN ST"


def test_property_record_null_fields():
    record = PropertyRecord.model_validate(make_property(location=None, assessed_total=None, lot_size_acres=None))
    assert record.location is None
    assert record.assessed_total is None
    assert record.lot_size_acres is None


def test_property_record_missing_parcel_id_raises():
    data = make_property()
    del data["parcel_id"]
    with pytest.raises(ValidationError):
        PropertyRecord.model_validate(data)


def test_sale_record_parses_date_string():
    sale = SaleRecord.model_validate({"sale_date": "06/15/2021", "sale_price": 350000})
    assert sale.sale_date == date(2021, 6, 15)


def test_sale_record_bad_date_returns_none():
    sale = SaleRecord.model_validate({"sale_date": "not-a-date"})
    assert sale.sale_date is None


def test_sale_record_null_date_returns_none():
    sale = SaleRecord.model_validate({"sale_date": None})
    assert sale.sale_date is None


def test_property_record_sales_parsed():
    record = PropertyRecord.model_validate(make_property(sales=[
        {"sale_date": "01/01/2020", "sale_price": 200000, "grantee": "JONES", "grantor": "SMITH"}
    ]))
    assert len(record.sales) == 1
    assert record.sales[0].sale_date == date(2020, 1, 1)
    assert record.sales[0].sale_price == 200000
