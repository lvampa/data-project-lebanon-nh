"""How the crossings backfill picks one spelling and one pin for a split crossing."""

from typing import Any

from scripts.normalize.crossings import CrossingRow, plan_groups


def row(row_id: int, text: str, **columns: Any) -> CrossingRow:
    values: dict[str, Any] = {
        "raw_address": f"RAW {row_id}",
        "source": "ai",
        "geocode_query": f"{text}, Lebanon, NH",
        "entries": 1,
        **columns,
    }
    return CrossingRow(id=row_id, normalized_address=text, **values)


def placed(
    row_id: int, text: str, precision: str = "exact", **columns: Any
) -> CrossingRow:
    pin: dict[str, Any] = {
        "lat": 43.64 + row_id / 1000,
        "lng": -72.25,
        "coordinate_precision": precision,
        "geocoded_via": "nominatim",
        **columns,
    }
    return row(row_id, text, **pin)


def targets(groups) -> dict[int, str]:
    return {r.row.id: r.normalized_address for g in groups for r in g.rewrites}


def test_a_crossing_spelled_in_both_orders_goes_to_the_most_used_one_in_order():
    groups = plan_groups(
        [
            row(1, "Poverty Ln and Mechanic St", entries=2),
            row(2, "Mechanic St and Poverty Ln", entries=5),
        ]
    )

    assert targets(groups) == {
        1: "Mechanic St and Poverty Ln",
        2: "Mechanic St and Poverty Ln",
    }
    [group] = groups
    assert group.target == "Mechanic St and Poverty Ln"


def test_a_case_difference_goes_to_the_most_used_spelling():
    groups = plan_groups(
        [
            row(1, "Lahaye St and Main St", entries=1),
            row(2, "LaHaye St and Main St", entries=9),
        ]
    )

    assert set(targets(groups).values()) == {"LaHaye St and Main St"}


def test_a_three_way_split_becomes_one_text():
    groups = plan_groups(
        [
            row(1, "Mechanic St and Poverty Ln", entries=3),
            row(2, "Poverty Ln and Mechanic St", entries=2),
            row(3, "poverty ln and Mechanic St", entries=1),
        ]
    )

    assert len(groups) == 1
    assert set(targets(groups).values()) == {"Mechanic St and Poverty Ln"}


def test_the_geocode_query_follows_the_new_text():
    [group] = plan_groups(
        [row(1, "Poverty Ln and Mechanic St"), row(2, "Mechanic St and Poverty Ln")]
    )

    assert {r.geocode_query for r in group.rewrites} == {
        "Mechanic St and Poverty Ln, Lebanon, NH"
    }


def test_a_tie_in_use_goes_to_the_first_text():
    groups = plan_groups(
        [
            row(1, "Main St and Elm St", entries=2),
            row(2, "Main St and elm St", entries=2),
        ]
    )

    assert len(set(targets(groups).values())) == 1


def test_a_crossing_already_in_one_spelling_and_one_pin_is_left_out():
    groups = plan_groups(
        [
            placed(1, "Elm St and Main St", lat=43.641, lng=-72.25),
            placed(2, "Elm St and Main St", lat=43.641, lng=-72.25),
        ]
    )

    assert groups == []


def test_a_crossing_in_one_spelling_is_left_alone_even_out_of_order():
    # A new spelling of it takes this text, so it never splits, and rewriting it would
    # only change the id of its pin.
    assert plan_groups([row(1, "Poverty Ln and Mechanic St")]) == []
    assert (
        plan_groups(
            [row(1, "Poverty Ln and Mechanic St"), row(2, "Poverty Ln and Mechanic St")]
        )
        == []
    )


def test_one_spelling_with_two_pins_is_brought_to_one_pin():
    rows = [
        placed(1, "Elm St and Main St", "exact"),
        placed(2, "Elm St and Main St", "approximate"),
    ]

    [group] = plan_groups(rows)

    assert [r.row.id for r in group.rewrites if r.pin_changed] == [2]
    assert not any(r.text_changed for r in group.rewrites)


def test_a_place_with_and_in_its_name_is_not_a_crossing():
    assert plan_groups([row(1, "Wright and Sons, Main St")]) == []


def test_a_human_rows_spelling_is_the_target_as_it_was_typed():
    groups = plan_groups(
        [
            row(1, "Mechanic St and Poverty Ln", entries=50),
            row(2, "Poverty Ln and mechanic St", entries=1, source="human"),
        ]
    )

    [group] = groups
    assert group.target == "Poverty Ln and mechanic St"
    assert targets(groups) == {1: "Poverty Ln and mechanic St"}
    assert [h.id for h in group.human] == [2]


def test_a_human_row_is_never_rewritten_but_is_listed():
    [group] = plan_groups(
        [row(1, "B St and A St"), row(2, "A St and B St", source="human")]
    )

    assert [r.row.id for r in group.rewrites] == [1]
    assert [h.id for h in group.human] == [2]


def test_every_row_takes_the_exact_pin_of_the_group():
    rows = [
        row(1, "Poverty Ln and Mechanic St"),
        placed(2, "Mechanic St and Poverty Ln", "approximate"),
        placed(3, "Mechanic St and Poverty Ln", "exact"),
        placed(4, "Mechanic St and Poverty Ln", "exact"),
    ]

    [group] = plan_groups(rows)

    pins = {r.row.id: r.pin for r in group.rewrites}
    assert set(pins.values()) == {rows[2].pin()}
    assert pins[1][0] == 43.643


def test_a_group_whose_only_pin_is_approximate_changes_its_text_and_copies_no_pin():
    rows = [
        row(1, "Poverty Ln and Mechanic St"),
        placed(2, "Mechanic St and Poverty Ln", "approximate"),
    ]

    [group] = plan_groups(rows)

    by_id = {r.row.id: r for r in group.rewrites}
    assert by_id[1].pin == rows[0].pin()
    assert not by_id[1].pin_changed
    assert not by_id[2].pin_changed
    assert by_id[1].text_changed


def test_an_approximate_pin_gives_way_to_an_exact_one_but_is_never_spread():
    rows = [
        placed(1, "Poverty Ln and Mechanic St", "approximate"),
        placed(2, "Mechanic St and Poverty Ln", "exact"),
        row(3, "poverty Ln and Mechanic St"),
    ]

    [group] = plan_groups(rows)

    assert {r.pin for r in group.rewrites} == {rows[1].pin()}


def test_the_lowest_id_wins_among_equal_pins():
    rows = [
        placed(5, "Poverty Ln and Mechanic St", "exact"),
        placed(3, "Mechanic St and Poverty Ln", "exact"),
    ]

    [group] = plan_groups(rows)

    assert {r.pin for r in group.rewrites} == {rows[1].pin()}


def test_a_human_rows_pin_is_the_best_pin_whatever_its_precision():
    rows = [
        placed(1, "Poverty Ln and Mechanic St", "exact"),
        placed(2, "Mechanic St and Poverty Ln", "approximate", source="human"),
    ]

    [group] = plan_groups(rows)

    assert [r.pin for r in group.rewrites] == [rows[1].pin()]


def test_a_group_with_no_pin_anywhere_changes_only_its_text():
    [group] = plan_groups(
        [row(1, "Poverty Ln and Mechanic St"), row(2, "Mechanic St and Poverty Ln")]
    )

    assert all(not r.pin_changed for r in group.rewrites)
    assert [r.text_changed for r in group.rewrites] == [True, False]


def test_a_row_with_a_pin_keeps_all_six_fields_of_the_winner():
    winner = row(
        1,
        "Mechanic St and Poverty Ln",
        lat=43.64,
        lng=-72.25,
        coordinate_precision="exact",
        geocoded_via="osm",
        osm_ref="node/9",
        geocode_source_url=None,
    )
    loser = row(
        2,
        "Poverty Ln and Mechanic St",
        lat=43.65,
        lng=-72.26,
        coordinate_precision="approximate",
        geocoded_via="nominatim",
    )

    [group] = plan_groups([winner, loser])

    moved = next(r for r in group.rewrites if r.row.id == 2)
    assert moved.pin == (43.64, -72.25, "exact", "osm", "node/9", None)
