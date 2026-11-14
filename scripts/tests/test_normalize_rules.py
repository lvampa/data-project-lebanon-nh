from datetime import datetime

from locations.canonical import RULES_VERSION, canonical_address
from postgres.models.property import Property

from scripts.normalize.rules import (
    CanonicalLocation,
    PlaceNormalization,
    RuleNormalization,
    apply_rules,
    rules_prompt_version,
)
from scripts.normalize.streets import load_street_list, streets_from_locations

STREETS = {"ELM ST", "MAIN ST", "MARKET ST", "N PLAINFIELD RD"}


def location(raw: str, place_code: str | None = None) -> CanonicalLocation:
    return CanonicalLocation(canonical_address(raw), place_code)


def settled(result) -> dict[str, RuleNormalization]:
    return {rule.canonical: rule for rule in result.settled}


def leftovers(result) -> list[str]:
    return [item.canonical for item in result.leftovers]


# --- the street list ---


def test_house_numbers_and_units_come_off_and_spellings_are_folded():
    streets = streets_from_locations(
        [
            "12 Main Street",
            "14 MAIN ST",
            "Main St Apt 3",
            "7 Elm St Unit #2",
            "340 North Plainfield Road",
        ]
    )

    assert streets == ["ELM ST", "MAIN ST", "N PLAINFIELD RD"]


def test_blank_and_missing_locations_are_skipped():
    assert streets_from_locations([None, "", "   ", "9 Oak St"]) == ["OAK ST"]


def test_the_street_list_is_distinct_and_sorted():
    streets = streets_from_locations(["2 Zed St", "1 Abe St", "3 Zed St"])

    assert streets == ["ABE ST", "ZED ST"]


def test_the_street_list_is_built_from_the_properties_table(db_session):
    now = datetime(2026, 11, 13)
    db_session.add_all(
        [
            Property(
                parcel_id="1", location="12 Main Street", created_at=now, updated_at=now
            ),
            Property(
                parcel_id="2", location="14 Main St", created_at=now, updated_at=now
            ),
            Property(parcel_id="3", location=None, created_at=now, updated_at=now),
            Property(
                parcel_id="4", location="7 Elm St", created_at=now, updated_at=now
            ),
        ]
    )
    db_session.commit()

    assert load_street_list(db_session) == ["ELM ST", "MAIN ST"]


def test_an_empty_properties_table_gives_an_empty_street_list(db_session):
    assert load_street_list(db_session) == []


# --- 6.15: a house number on a listed street ---


def test_a_house_number_on_a_listed_street_is_an_address():
    result = apply_rules([location("12 Main Street")], STREETS, places={})

    rule = settled(result)["12 MAIN ST"]
    assert rule.kind == "address"
    assert rule.normalized_address == "12 MAIN ST"
    assert rule.geocode_query == "12 MAIN ST, Lebanon, NH"
    assert leftovers(result) == []


def test_a_unit_does_not_stop_a_listed_address_and_is_not_kept():
    result = apply_rules([location("12 Main St Apt 3")], STREETS, places={})

    rule = settled(result)["12 MAIN ST APT 3"]
    assert (rule.kind, rule.normalized_address) == ("address", "12 MAIN ST")


def test_a_direction_and_suffix_spelling_still_matches_the_listed_street():
    result = apply_rules([location("340 North Plainfield Road")], STREETS, places={})

    assert settled(result)["340 N PLAINFIELD RD"].kind == "address"


def test_a_house_number_on_an_unlisted_street_is_a_leftover():
    result = apply_rules([location("12 Oak St")], STREETS, places={})

    assert result.settled == []
    assert leftovers(result) == ["12 OAK ST"]


# --- 6.16: two listed streets ---


def test_two_listed_streets_joined_by_and_are_an_intersection():
    result = apply_rules([location("Main St and Elm St")], STREETS, places={})

    rule = settled(result)["MAIN ST & ELM ST"]
    assert rule.kind == "intersection"
    assert rule.normalized_address == "MAIN ST and ELM ST"
    assert rule.geocode_query == "MAIN ST and ELM ST, Lebanon, NH"


def test_an_ampersand_or_slash_makes_the_same_intersection():
    result = apply_rules(
        [location("Main St & Elm St"), location("Market St/Elm St")],
        STREETS,
        places={},
    )

    assert {rule.kind for rule in result.settled} == {"intersection"}
    assert len(result.settled) == 2


def test_an_intersection_with_one_unlisted_street_is_a_leftover():
    result = apply_rules([location("Main St and Oak St")], STREETS, places={})

    assert result.settled == []
    assert leftovers(result) == ["MAIN ST & OAK ST"]


def test_three_streets_are_not_an_intersection():
    result = apply_rules(
        [location("Main St and Elm St and Market St")], STREETS, places={}
    )

    assert result.settled == []


# --- 6.17: a known place code ---

HANNAFORD = PlaceNormalization(normalized_address="Hannaford, Market St", kind="place")


def test_a_known_place_code_copies_its_address_and_kind():
    result = apply_rules(
        [location("HANNAFORDS MARKET - MARKET ST", place_code="L HANNAF")],
        STREETS,
        places={"L HANNAF": HANNAFORD},
    )

    rule = settled(result)["HANNAFORDS MARKET - MARKET ST"]
    assert rule.kind == "place"
    assert rule.normalized_address == "Hannaford, Market St"
    assert rule.geocode_query == "Hannaford, Market St, Lebanon, NH"


def test_an_unknown_place_code_leaves_the_location_for_ai():
    result = apply_rules(
        [location("BEST BUY - PLAINFIELD RD", place_code="L BESTB")],
        STREETS,
        places={"L HANNAF": HANNAFORD},
    )

    assert result.settled == []
    assert leftovers(result) == ["BEST BUY - PLAINFIELD RD"]


def test_a_location_with_no_place_code_never_uses_the_place_map():
    result = apply_rules(
        [location("HANNAFORDS MARKET - MARKET ST", place_code=None)],
        STREETS,
        places={"L HANNAF": HANNAFORD},
    )

    assert result.settled == []


def test_an_address_rule_comes_before_the_place_code_rule():
    result = apply_rules(
        [location("12 Main St", place_code="L HANNAF")],
        STREETS,
        places={"L HANNAF": HANNAFORD},
    )

    assert settled(result)["12 MAIN ST"].kind == "address"


# --- what the rules leave for AI ---


def test_a_bare_street_name_is_a_leftover():
    result = apply_rules([location("Main St")], STREETS, places={})

    assert result.settled == []
    assert leftovers(result) == ["MAIN ST"]


def test_a_highway_reference_is_a_leftover():
    result = apply_rules([location("I-89 NB MM 18")], STREETS, places={})

    assert leftovers(result) == ["I-89 NB MM 18"]


def test_with_an_empty_street_list_only_place_codes_can_settle_a_location():
    result = apply_rules(
        [location("12 Main St"), location("HANNAFORDS - MARKET ST", "L HANNAF")],
        streets=set(),
        places={"L HANNAF": HANNAFORD},
    )

    assert [rule.kind for rule in result.settled] == ["place"]
    assert leftovers(result) == ["12 MAIN ST"]


def test_every_location_is_either_settled_or_left_over_exactly_once():
    inputs = [
        location("12 Main St"),
        location("Main St and Elm St"),
        location("Oak St"),
        location("HANNAFORDS - MARKET ST", "L HANNAF"),
    ]

    result = apply_rules(inputs, STREETS, places={"L HANNAF": HANNAFORD})

    assert len(result.settled) + len(result.leftovers) == len(inputs)


# --- the version rule rows carry ---


def test_a_rule_rows_prompt_version_names_the_rules_version():
    assert rules_prompt_version() == f"rules-{RULES_VERSION}"
