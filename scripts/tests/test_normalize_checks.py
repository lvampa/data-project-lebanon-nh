import pytest

from scripts.normalize.checks import (
    AnswerOffSchema,
    check_incident_types,
    check_locations,
)


def type_item(raw: str, **overrides: object) -> dict[str, object]:
    return {
        "raw": raw,
        "category": "Traffic",
        "normalized_type": "Motor vehicle complaint",
        "unsure": False,
        **overrides,
    }


def location_item(raw: str, **overrides: object) -> dict[str, object]:
    return {
        "raw": raw,
        "kind": "address",
        "normalized_address": "12 Main St",
        "geocode_query": "12 Main St, Lebanon, NH",
        "street": "Main St",
        "unsure": False,
        **overrides,
    }


def raws(accepted) -> list[str]:
    return [entry.item.raw for entry in accepted]


# --- the answer as a whole (8.2) ---


@pytest.mark.parametrize(
    "answer",
    [{}, {"items": "nope"}, {"other": 1}, [], "text", None],
    ids=["empty", "items_not_a_list", "wrong_key", "list", "text", "none"],
)
def test_an_empty_or_off_schema_answer_is_refused_whole(answer):
    with pytest.raises(AnswerOffSchema):
        check_incident_types(answer, sent=["MV COMPLAINT"], names_in_use=[])


def test_an_answer_with_an_empty_item_list_leaves_every_value_missing():
    # Missing values get a failed attempt, so a batch the model always answers with
    # nothing reaches the attempt limit instead of being sent again every run.
    checked = check_incident_types(
        {"items": []}, sent=["MV COMPLAINT", "NOISE"], names_in_use=[]
    )

    assert checked.accepted == []
    assert checked.missing == ["MV COMPLAINT", "NOISE"]


# --- shared rules, shown on incident types ---


def test_a_complete_valid_answer_is_all_accepted():
    answer = {
        "items": [
            type_item("MV COMPLAINT"),
            type_item("NOISE", category="Police", normalized_type="Noise complaint"),
        ]
    }

    checked = check_incident_types(
        answer, sent=["MV COMPLAINT", "NOISE"], names_in_use=[]
    )

    assert raws(checked.accepted) == ["MV COMPLAINT", "NOISE"]
    assert checked.discarded == []
    assert checked.missing == []
    assert not any(entry.needs_review for entry in checked.accepted)


def test_an_item_for_a_value_that_was_not_sent_is_discarded():
    answer = {"items": [type_item("MV COMPLAINT"), type_item("INVENTED")]}

    checked = check_incident_types(answer, sent=["MV COMPLAINT"], names_in_use=[])

    assert raws(checked.accepted) == ["MV COMPLAINT"]
    # A value the job never sent is not a value it can charge an attempt to.
    assert checked.discarded == []
    assert checked.not_sent == ["INVENTED"]


def test_a_value_that_comes_back_twice_is_discarded_both_times_and_not_missing():
    answer = {
        "items": [
            type_item("MV COMPLAINT"),
            type_item("MV COMPLAINT"),
            type_item("NOISE"),
        ]
    }

    checked = check_incident_types(
        answer, sent=["MV COMPLAINT", "NOISE"], names_in_use=[]
    )

    assert raws(checked.accepted) == ["NOISE"]
    assert [(d.raw, d.reason) for d in checked.discarded] == [
        ("MV COMPLAINT", "returned more than once")
    ]
    assert checked.missing == []


def test_a_value_the_answer_leaves_out_is_missing():
    answer = {"items": [type_item("MV COMPLAINT")]}

    checked = check_incident_types(
        answer, sent=["MV COMPLAINT", "NOISE", "ALARM"], names_in_use=[]
    )

    assert raws(checked.accepted) == ["MV COMPLAINT"]
    assert checked.missing == ["NOISE", "ALARM"]
    assert checked.discarded == []


def test_an_item_with_a_category_outside_the_five_is_discarded_not_the_whole_answer():
    answer = {
        "items": [type_item("MV COMPLAINT", category="Parking"), type_item("NOISE")]
    }

    checked = check_incident_types(
        answer, sent=["MV COMPLAINT", "NOISE"], names_in_use=[]
    )

    assert raws(checked.accepted) == ["NOISE"]
    assert [(d.raw, d.reason) for d in checked.discarded] == [
        ("MV COMPLAINT", "invalid item")
    ]
    assert checked.missing == []


def test_an_item_that_is_not_an_object_leaves_its_value_missing():
    answer = {"items": ["MV COMPLAINT", type_item("NOISE")]}

    checked = check_incident_types(
        answer, sent=["MV COMPLAINT", "NOISE"], names_in_use=[]
    )

    assert raws(checked.accepted) == ["NOISE"]
    assert checked.missing == ["MV COMPLAINT"]


def test_an_unsure_item_is_accepted_with_a_review_mark():
    answer = {"items": [type_item("MV COMPLAINT", unsure=True), type_item("NOISE")]}

    checked = check_incident_types(
        answer, sent=["MV COMPLAINT", "NOISE"], names_in_use=[]
    )

    assert [(e.item.raw, e.needs_review) for e in checked.accepted] == [
        ("MV COMPLAINT", True),
        ("NOISE", False),
    ]


# --- incident types only ---


def test_a_name_with_a_dispatch_abbreviation_as_a_whole_word_is_discarded():
    answer = {"items": [type_item("MV COMPLAINT", normalized_type="MV complaint")]}

    checked = check_incident_types(answer, sent=["MV COMPLAINT"], names_in_use=[])

    assert checked.accepted == []
    assert [(d.raw, d.reason) for d in checked.discarded] == [
        ("MV COMPLAINT", "abbreviation in the name")
    ]


def test_an_abbreviation_inside_a_longer_word_is_not_a_match():
    answer = {"items": [type_item("ALARM", normalized_type="Mvasion alarm")]}

    checked = check_incident_types(answer, sent=["ALARM"], names_in_use=[])

    assert raws(checked.accepted) == ["ALARM"]


def test_a_name_that_differs_from_one_in_use_only_in_case_or_spacing_is_snapped():
    answer = {
        "items": [type_item("MV COMPLAINT", normalized_type="motor  vehicle COMPLAINT")]
    }

    checked = check_incident_types(
        answer, sent=["MV COMPLAINT"], names_in_use=["Motor vehicle complaint"]
    )

    assert checked.accepted[0].item.normalized_type == "Motor vehicle complaint"


def test_a_new_name_is_kept_as_it_came():
    answer = {"items": [type_item("NOISE", normalized_type="Noise complaint")]}

    checked = check_incident_types(
        answer, sent=["NOISE"], names_in_use=["Motor vehicle complaint"]
    )

    assert checked.accepted[0].item.normalized_type == "Noise complaint"


# --- locations ---

STREETS = ["ELM ST", "MAIN ST", "MARKET ST"]


def test_a_location_on_a_listed_street_is_accepted_without_a_mark():
    answer = {"items": [location_item("12 MAIN STREET")]}

    checked = check_locations(answer, sent=["12 MAIN STREET"], streets=STREETS)

    assert [(e.item.raw, e.needs_review) for e in checked.accepted] == [
        ("12 MAIN STREET", False)
    ]


def test_the_answers_street_is_compared_in_canonical_form():
    answer = {"items": [location_item("12 MAIN STREET", street="Main Street")]}

    checked = check_locations(answer, sent=["12 MAIN STREET"], streets=STREETS)

    assert checked.accepted[0].needs_review is False


def test_a_street_not_on_the_list_is_accepted_with_a_review_mark():
    answer = {"items": [location_item("RT 4", kind="highway", street="Route 4")]}

    checked = check_locations(answer, sent=["RT 4"], streets=STREETS)

    assert [(e.item.raw, e.needs_review) for e in checked.accepted] == [("RT 4", True)]
    assert checked.discarded == []


def test_an_empty_street_is_not_checked_against_the_list():
    answer = {"items": [location_item("WALMART", kind="place", street="")]}

    checked = check_locations(answer, sent=["WALMART"], streets=STREETS)

    assert checked.accepted[0].needs_review is False


def test_an_unsure_location_is_accepted_with_a_review_mark_even_on_a_listed_street():
    answer = {"items": [location_item("12 MAIN STREET", unsure=True)]}

    checked = check_locations(answer, sent=["12 MAIN STREET"], streets=STREETS)

    assert checked.accepted[0].needs_review is True


def test_a_location_with_an_unknown_kind_is_discarded():
    answer = {"items": [location_item("12 MAIN STREET", kind="landmark")]}

    checked = check_locations(answer, sent=["12 MAIN STREET"], streets=STREETS)

    assert checked.accepted == []
    assert [d.raw for d in checked.discarded] == ["12 MAIN STREET"]


def test_locations_share_the_not_sent_twice_and_missing_rules():
    answer = {
        "items": [
            location_item("A"),
            location_item("A"),
            location_item("NOT SENT"),
        ]
    }

    checked = check_locations(answer, sent=["A", "B"], streets=STREETS)

    assert checked.accepted == []
    assert [(d.raw, d.reason) for d in checked.discarded] == [
        ("A", "returned more than once")
    ]
    assert checked.not_sent == ["NOT SENT"]
    assert checked.missing == ["B"]
