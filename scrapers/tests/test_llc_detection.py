import pytest
from pipelines import _LLC_PATTERN as LLC_PATTERN


@pytest.mark.parametrize(
    "owner",
    [
        "ANAGNOST UPPER VALLEY LLC",
        "MISTER DITHERS LLC",
        "BUSTER & BLONDIE LLC",
        "SOME CORP",
        "ACME CORPORATION",
        "CLARKE & DUSTIN REV FAM TRUST",
        "SOME INC",
        "PARTNERS LP",
        "LAWYERS LLP",
        "DOCTORS PLLC",
        "anagnost upper valley llc",  # case-insensitive
        "SMITH L.L.C.",
    ],
)
def test_matches_entity_patterns(owner):
    assert LLC_PATTERN.search(owner)


@pytest.mark.parametrize(
    "owner",
    [
        "PAGE, SALLY TRUSTEE",  # TRUSTEE not TRUST
        "SMITH, JOHN",
        "DOE, JANE",
        "",
    ],
)
def test_does_not_match_individuals(owner):
    assert not LLC_PATTERN.search(owner)
