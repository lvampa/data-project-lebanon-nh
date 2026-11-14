import hashlib
from importlib import resources

import pytest
from locations.canonical import (
    RULES_VERSION,
    canonical_address,
    split_house_number,
    strip_unit,
)

# Spellings that must reach the same canonical form.
SAME = [
    # case, spacing, and punctuation
    ("Main St", "MAIN ST"),
    ("  main   st  ", "MAIN ST"),
    ("MAIN ST.", "MAIN ST"),
    ("12 Main St.", "12 MAIN ST"),
    ("12  MAIN\tST", "12 MAIN ST"),
    ("Hannaford's Market - Market St", "HANNAFORDS MARKET - MARKET ST"),
    ("HANNAFORD'S MARKET   -   MARKET ST", "HANNAFORDS MARKET - MARKET ST"),
    # suffix spellings
    ("12 Main Street", "12 MAIN ST"),
    ("12 Main Str", "12 MAIN ST"),
    ("340 Mechanic Avenue", "340 MECHANIC AVE"),
    ("340 Mechanic Av", "340 MECHANIC AVE"),
    ("Eagle Ridge Road", "EAGLE RIDGE RD"),
    ("Timberwood Drive", "TIMBERWOOD DR"),
    ("Poverty Lane", "POVERTY LN"),
    ("Heater Road Extension", "HEATER RD EXT"),
    ("Etna Highway", "ETNA HWY"),
    ("River Boulevard", "RIVER BLVD"),
    ("Verona Terrace", "VERONA TER"),
    # direction spellings
    ("North Main Street", "N MAIN ST"),
    ("N. Main St", "N MAIN ST"),
    ("Main Street North", "MAIN ST N"),
    ("Park Street Northeast", "PARK ST NE"),
    # a word that is a suffix spelling is only abbreviated at the end of a street
    ("Pine Street", "PINE ST"),
    ("Park Avenue", "PARK AVE"),
    # intersections: and, &, and / all give one joiner
    ("Main St and Elm St", "MAIN ST & ELM ST"),
    ("Main Street & Elm Street", "MAIN ST & ELM ST"),
    ("MAIN ST/ELM ST", "MAIN ST & ELM ST"),
    ("Main St / Elm St", "MAIN ST & ELM ST"),
    # units
    ("12 Main St Apartment 3", "12 MAIN ST APT 3"),
    ("12 Main St Suite 200", "12 MAIN ST STE 200"),
    ("12 Main St #3", "12 MAIN ST UNIT 3"),
    ("12 Main St # 3", "12 MAIN ST UNIT 3"),
    ("12 Main St Unit #3", "12 MAIN ST UNIT 3"),
    ("12 Main St Apt #3", "12 MAIN ST APT 3"),
]

# Different places that must not collapse into one.
DIFFERENT = [
    ("12 Main St", "21 Main St"),
    ("Main St", "Main Ave"),
    ("North Main St", "South Main St"),
    ("Main St & Elm St", "Main St & Oak St"),
    ("12 Main St Apt 3", "12 Main St Apt 4"),
    ("Pine St", "Pine Ave"),
    ("I-89 NB MM 18", "I-89 SB MM 18"),
]


@pytest.mark.parametrize(("raw", "canonical"), SAME)
def test_spellings_reach_the_same_canonical_form(raw, canonical):
    assert canonical_address(raw) == canonical


@pytest.mark.parametrize(("first", "second"), DIFFERENT)
def test_different_places_stay_different(first, second):
    assert canonical_address(first) != canonical_address(second)


@pytest.mark.parametrize(("raw", "canonical"), SAME)
def test_a_canonical_form_is_its_own_canonical_form(raw, canonical):
    assert canonical_address(canonical) == canonical


def test_a_highway_reference_keeps_its_hyphen_and_direction_letters():
    assert canonical_address("I-89 N/B MM 18") == "I-89 N/B MM 18"
    assert canonical_address("i-89 nb mm 18") == "I-89 NB MM 18"


def test_a_slash_between_short_tokens_is_not_an_intersection():
    assert "&" not in canonical_address("I-89 S/B")


def test_empty_and_blank_input_is_an_empty_string():
    assert canonical_address("") == ""
    assert canonical_address("   ") == ""


# --- split_house_number ---


@pytest.mark.parametrize(
    ("canonical", "expected"),
    [
        ("12 MAIN ST", ("12", "MAIN ST")),
        ("12A MAIN ST", ("12A", "MAIN ST")),
        ("12-14 MAIN ST", ("12-14", "MAIN ST")),
        ("340 N MAIN ST", ("340", "N MAIN ST")),
        ("MAIN ST", (None, "MAIN ST")),
        ("I-89 NB MM 18", (None, "I-89 NB MM 18")),
        ("12", (None, "12")),
        ("", (None, "")),
    ],
)
def test_the_house_number_is_split_from_the_street(canonical, expected):
    assert split_house_number(canonical) == expected


# --- strip_unit ---


@pytest.mark.parametrize(
    ("canonical", "expected"),
    [
        ("12 MAIN ST UNIT 3", ("12 MAIN ST", "UNIT 3")),
        ("12 MAIN ST APT 4B", ("12 MAIN ST", "APT 4B")),
        ("12 MAIN ST STE 200", ("12 MAIN ST", "STE 200")),
        ("12 MAIN ST", ("12 MAIN ST", None)),
        ("MAIN ST & ELM ST", ("MAIN ST & ELM ST", None)),
    ],
)
def test_the_unit_is_split_off_the_end(canonical, expected):
    assert strip_unit(canonical) == expected


def test_a_street_named_like_a_unit_word_is_not_stripped():
    assert strip_unit("12 SUITE ST") == ("12 SUITE ST", None)


# --- the rules version ---

# The hash of street_suffixes.csv when RULES_VERSION was last set. Changing the file
# changes parsed values, so it comes with a RULES_VERSION bump (rule rows record it).
SUFFIX_FILE_SHA256 = "543097cf3545ba8d71b438aeec217a68c9bdbdfb17900ae1f43e0d3a0d6a0bd2"
SUFFIX_FILE_VERSION = "1"


def test_the_rules_version_is_bumped_when_the_suffix_file_changes():
    data = resources.files("locations").joinpath("street_suffixes.csv").read_bytes()
    digest = hashlib.sha256(data).hexdigest()

    if digest != SUFFIX_FILE_SHA256:
        pytest.fail(
            "street_suffixes.csv changed. Bump RULES_VERSION in canonical.py, then set "
            f"SUFFIX_FILE_VERSION and SUFFIX_FILE_SHA256 here to the new values "
            f"({digest})."
        )
    assert RULES_VERSION == SUFFIX_FILE_VERSION
