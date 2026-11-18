import pytest

from scripts.models.property import PropertyRecord, SaleRecord
from scripts.properties.checks import (
    check_core_fields,
    check_count,
    check_sales,
    check_unique_mblu,
)


def parcel(number: int, **fields) -> PropertyRecord:
    values = {
        "vgsi_pid": str(number),
        "mblu": f"{number}/1///",
        "location": "1 MAIN ST",
        "owner": "SOMEONE",
        "assessed_total": 100,
        "sales": [SaleRecord(owner="SOMEONE")],
    }
    return PropertyRecord.model_validate({**values, **fields})


@pytest.mark.parametrize(
    ("parsed", "current", "passes"),
    [
        (3000, 0, True),
        (2999, 0, False),
        (1100, 1000, True),
        (1101, 1000, False),
        (900, 1000, True),
        (899, 1000, False),
    ],
)
def test_count_needs_the_floor_on_a_first_build_and_a_steady_total_after(
    parsed, current, passes
):
    assert check_count(parsed, current).passed is passes


def test_core_fields_allow_five_percent_empty():
    nineteen = [parcel(n) for n in range(19)]

    assert check_core_fields([*nineteen, parcel(99, owner=None)]).passed
    assert not check_core_fields(
        [*nineteen, parcel(98, owner=None), parcel(99, owner=None)]
    ).passed


def test_core_fields_name_the_empty_field():
    result = check_core_fields([parcel(1, assessed_total=None)])

    assert not result.passed
    assert "assessed_total 100.0%" in result.detail


def test_two_parcels_may_not_share_an_mblu():
    assert check_unique_mblu([parcel(1), parcel(2)]).passed

    result = check_unique_mblu([parcel(1), parcel(2, mblu="1/1///")])

    assert not result.passed
    assert "1/1///" in result.detail


def test_half_the_parcels_need_a_sale():
    without = parcel(2, sales=[])

    assert check_sales([parcel(1), without]).passed
    assert not check_sales([parcel(1), without, parcel(3, sales=[])]).passed


def test_checks_fail_on_no_parcels():
    assert not check_core_fields([]).passed
    assert not check_sales([]).passed
