import json

import pytest
from locations.geocode import in_city_bounds
from locations.osm import (
    Snapshot,
    locate_address,
    locate_intersection,
    locate_road,
    names_the_road,
    place_candidates,
    route_refs,
    snapshot_from_replies,
)


def way(way_id: int, name: str, *nodes: tuple[int, float, float]) -> dict:
    return {
        "type": "way",
        "id": way_id,
        "tags": {"highway": "residential", "name": name},
        "nodes": [n[0] for n in nodes],
        "geometry": [{"lat": n[1], "lon": n[2]} for n in nodes],
    }


def feature(kind: str, feature_id: int, lat: float, lon: float, **tags: str) -> dict:
    where = (
        {"lat": lat, "lon": lon}
        if kind == "node"
        else {"center": {"lat": lat, "lon": lon}}
    )
    return {"type": kind, "id": feature_id, "tags": tags, **where}


# Mount Support Road runs east to west. Dartmouth Avenue crosses it at node 2.
ROADS = [
    way(
        1,
        "Mount Support Road",
        (1, 43.6740, -72.2700),
        (2, 43.6740, -72.2650),
        (3, 43.6740, -72.2600),
    ),
    way(2, "Dartmouth Avenue", (4, 43.6700, -72.2650), (2, 43.6740, -72.2650)),
    way(3, "Commerce Avenue", (5, 43.6500, -72.2500), (6, 43.6500, -72.2450)),
]
FEATURES = [
    feature(
        "way",
        10,
        43.6501,
        -72.2480,
        **{
            "addr:housenumber": "8",
            "addr:street": "Commerce Avenue",
            "building": "yes",
        },
    ),
    feature(
        "node",
        11,
        43.6745,
        -72.2640,
        name="Quarry Hill Town Houses",
        building="apartments",
    ),
    feature(
        "node",
        12,
        43.6746,
        -72.2655,
        name="Quarry Hill Town Houses Office",
        amenity="office",
    ),
    feature("node", 13, 43.6900, -72.2640, name="Quarry Hill Farm"),
    feature("node", 14, 43.6742, -72.2641, name="The Building at Quarry"),
]


def snapshot(
    features: list[dict] | None = None, roads: list[dict] | None = None
) -> Snapshot:
    return snapshot_from_replies(
        "2026-11-20",
        {"elements": FEATURES if features is None else features},
        {"elements": ROADS if roads is None else roads},
    )


def test_it_round_trips_through_json():
    original = snapshot()

    again = Snapshot.from_json(original.to_json())

    assert again.features == original.features
    assert again.roads == original.roads


def test_the_newest_file_is_loaded(tmp_path):
    (tmp_path / "snapshot-2026-01-01.json").write_text(
        snapshot_from_replies(
            "2026-01-01", {"elements": []}, {"elements": []}
        ).to_json()
    )
    (tmp_path / "snapshot-2026-11-20.json").write_text(snapshot().to_json())

    assert Snapshot.load_newest(tmp_path).fetched_at == "2026-11-20"


def test_a_missing_snapshot_says_how_to_make_one(tmp_path):
    with pytest.raises(FileNotFoundError, match="osm-snapshot"):
        Snapshot.load_newest(tmp_path)


# --- house addresses ---


def test_an_address_matches_the_number_and_street_in_any_spelling():
    match = locate_address(snapshot(), "8", "COMMERCE AVE")

    assert match is not None
    assert (match.lat, match.lng, match.osm_ref, match.via) == (
        43.6501,
        -72.2480,
        "way/10",
        "address",
    )


def test_an_address_with_no_such_number_or_street_is_a_miss():
    assert locate_address(snapshot(), "9", "COMMERCE AVE") is None
    assert locate_address(snapshot(), "8", "ELM ST") is None


def test_two_features_at_one_address_within_10_m_make_their_centroid():
    both = [
        feature(
            "way",
            20,
            43.65010,
            -72.24800,
            **{
                "addr:housenumber": "8",
                "addr:street": "Commerce Avenue",
                "building": "yes",
            },
        ),
        feature(
            "way",
            21,
            43.65014,
            -72.24800,
            **{
                "addr:housenumber": "8",
                "addr:street": "Commerce Avenue",
                "building": "yes",
            },
        ),
    ]

    match = locate_address(snapshot(both), "8", "COMMERCE AVE")

    assert match is not None
    assert match.lat == pytest.approx(43.65012)


def test_two_buildings_at_one_address_far_apart_are_a_miss():
    far = [
        feature(
            "way",
            20,
            43.6501,
            -72.2480,
            **{
                "addr:housenumber": "8",
                "addr:street": "Commerce Avenue",
                "building": "yes",
            },
        ),
        feature(
            "way",
            21,
            43.6511,
            -72.2480,
            **{
                "addr:housenumber": "8",
                "addr:street": "Commerce Avenue",
                "building": "yes",
            },
        ),
    ]

    assert locate_address(snapshot(far), "8", "COMMERCE AVE") is None


def test_a_building_is_preferred_to_a_point_with_the_same_address():
    mixed = [
        feature(
            "node",
            20,
            43.6600,
            -72.2400,
            **{"addr:housenumber": "8", "addr:street": "Commerce Avenue"},
        ),
        feature(
            "way",
            21,
            43.6501,
            -72.2480,
            **{
                "addr:housenumber": "8",
                "addr:street": "Commerce Avenue",
                "building": "yes",
            },
        ),
    ]

    match = locate_address(snapshot(mixed), "8", "COMMERCE AVE")

    assert match is not None and match.osm_ref == "way/21"


# --- intersections ---


def test_an_intersection_is_the_node_two_roads_share():
    match = locate_intersection(snapshot(), "MOUNT SUPPORT RD", "DARTMOUTH AVE")

    assert match is not None
    assert (match.lat, match.lng, match.osm_ref, match.via) == (
        43.6740,
        -72.2650,
        "node/2",
        "intersection",
    )


def test_roads_that_do_not_meet_are_a_miss():
    assert locate_intersection(snapshot(), "COMMERCE AVE", "DARTMOUTH AVE") is None


def test_an_unknown_street_is_a_miss():
    assert locate_intersection(snapshot(), "ELM ST", "DARTMOUTH AVE") is None


def divided(second_node: tuple[int, float, float]) -> list[dict]:
    return [
        way(
            1,
            "Main Street",
            (1, 43.6, -72.2),
            (2, 43.6500, -72.2500),
            (3, 43.6600, -72.2500),
        ),
        way(
            2,
            "Elm Street",
            (4, 43.64, -72.25),
            (2, 43.6500, -72.2500),
            second_node,
            (5, 43.67, -72.25),
        ),
    ]


def test_several_shared_nodes_within_150_m_give_their_centroid():
    near = [
        way(1, "Main Street", (1, 43.6500, -72.2500), (2, 43.6501, -72.2500)),
        way(2, "Elm Street", (1, 43.6500, -72.2500), (2, 43.6501, -72.2500)),
    ]

    match = locate_intersection(snapshot([], near), "MAIN ST", "ELM ST")

    assert match is not None
    assert match.lat == pytest.approx(43.65005)
    assert match.osm_ref == "node/1"


def test_shared_nodes_far_apart_are_a_miss():
    assert (
        locate_intersection(
            snapshot([], divided((3, 43.6600, -72.2500))), "MAIN ST", "ELM ST"
        )
        is None
    )


# --- named places ---


def test_candidates_share_a_word_and_lie_near_the_street_best_first():
    found = place_candidates(snapshot(), "QUARRY HILL TOWN HOUSES", "MOUNT SUPPORT RD")

    assert [c.feature.ref for c in found] == ["node/11", "node/12", "node/14"]


def test_a_feature_beyond_200_m_of_the_street_is_left_out():
    found = place_candidates(snapshot(), "QUARRY HILL FARM", "MOUNT SUPPORT RD")

    assert "node/13" not in [c.feature.ref for c in found]


def test_a_stop_word_alone_is_not_a_match():
    assert place_candidates(snapshot(), "THE BUILDING", "MOUNT SUPPORT RD") == []


def test_a_street_with_no_road_has_no_candidates():
    assert place_candidates(snapshot(), "QUARRY HILL", "ELM ST") == []


def test_only_the_top_candidates_are_kept():
    many = [
        feature("node", 100 + n, 43.6745, -72.2640, name=f"Quarry Hill {n}")
        for n in range(12)
    ]

    assert len(place_candidates(snapshot(many), "QUARRY HILL", "MOUNT SUPPORT RD")) == 8


def test_the_distance_to_the_street_is_in_meters():
    [first, *_] = place_candidates(
        snapshot(), "QUARRY HILL TOWN HOUSES", "MOUNT SUPPORT RD"
    )

    assert first.meters_from_street == pytest.approx(56, abs=2)


def test_a_node_in_the_shape_overpass_returns_is_parsed():
    reply = {
        "elements": [
            {
                "type": "node",
                "id": 123456,
                "lat": 43.665725,
                "lon": -72.2501,
                "tags": {"name": "Spruce Point", "leisure": "park"},
            }
        ]
    }

    parsed = snapshot_from_replies("2026-11-20", reply, {"elements": []})

    [feature] = parsed.features
    assert (feature.ref, feature.name, feature.kind) == (
        "node/123456",
        "Spruce Point",
        "leisure=park",
    )
    assert (feature.lat, feature.lng) == (43.665725, -72.2501)


# --- roads named by route number ---


def route_way(
    way_id: int, name: str | None, ref: str | None, *nodes: tuple[int, float, float]
) -> dict:
    tags = {"highway": "primary"}
    if name:
        tags["name"] = name
    if ref:
        tags["ref"] = ref
    return {
        "type": "way",
        "id": way_id,
        "tags": tags,
        "nodes": [n[0] for n in nodes],
        "geometry": [{"lat": n[1], "lon": n[2]} for n in nodes],
    }


# Route 120 is a named highway with a ref. Interstate 89 has a ref and no name. Hanover St
# crosses both. A short way and a longer way share the ref "NH 4A;US 4".
ROUTES = [
    route_way(
        1,
        "Dartmouth College Highway",
        "NH 120",
        (1, 43.65, -72.30),
        (2, 43.65, -72.25),
        (3, 43.65, -72.20),
    ),
    route_way(
        2, None, "I 89", (10, 43.60, -72.30), (11, 43.64, -72.25), (12, 43.68, -72.20)
    ),
    route_way(3, "Hanover St", None, (20, 43.64, -72.25), (2, 43.65, -72.25)),
    route_way(4, "Hanover St", None, (11, 43.64, -72.25), (21, 43.60, -72.25)),
    route_way(5, "Short Road", "NH 4A;US 4", (30, 43.66, -72.28), (31, 43.661, -72.28)),
    route_way(
        6,
        "Long Road",
        "NH 4A;US 4",
        (40, 43.66, -72.24),
        (41, 43.67, -72.24),
        (42, 43.69, -72.24),
    ),
]


def route_snapshot(ways: list[dict] | None = None) -> Snapshot:
    return snapshot_from_replies(
        "2026-11-23", {"elements": []}, {"elements": ROUTES if ways is None else ways}
    )


@pytest.mark.parametrize(
    ("text", "refs"),
    [
        ("ROUTE 120", {"NH 120", "US 120"}),
        ("RT 120", {"NH 120", "US 120"}),
        ("RTE 120", {"NH 120", "US 120"}),
        ("NH 120", {"NH 120"}),
        ("NH ROUTE 120", {"NH 120"}),
        ("STATE ROUTE 120", {"NH 120"}),
        ("State Route 4A", {"NH 4A"}),
        ("INTERSTATE 89", {"I 89"}),
        ("I-89", {"I 89"}),
        ("I 89", {"I 89"}),
        ("US 4", {"US 4"}),
        ("U.S. 4", {"US 4"}),
        ("US ROUTE 4", {"US 4"}),
        ("ROUTE 4", {"NH 4", "US 4"}),
        ("ROUTE 12A", {"NH 12A", "US 12A"}),
    ],
)
def test_a_route_written_the_way_the_log_writes_it_has_its_refs(text, refs):
    assert route_refs(text) == refs


@pytest.mark.parametrize(
    "text",
    [
        "Main St",
        "ROUTE",
        "ROUTE 1200",
        "BUS 4",
        "ROCK CUT - ROUTE 120",
        "120",
        "I",
        "ROUTE 120 NORTH",
    ],
)
def test_text_that_is_not_only_a_route_has_no_refs(text):
    assert route_refs(text) == set()


def test_a_route_number_is_found_inside_other_words_when_asked():
    assert route_refs("ROCK CUT - ROUTE 120", anywhere=True) == {"NH 120", "US 120"}
    assert route_refs("I-89 NORTHBOUND", anywhere=True) == {"I 89"}
    assert route_refs("BUS 4 STOP", anywhere=True) == set()


def test_an_interstate_never_matches_a_state_or_federal_route():
    assert "I 89" not in route_refs("ROUTE 89")
    assert route_refs("I 89") == {"I 89"}


def test_a_log_route_finds_the_way_with_that_ref_whatever_its_name():
    found = route_snapshot().roads_named("ROUTE 120")

    assert [road.name for road in found] == ["Dartmouth College Highway"]


def test_a_way_with_a_ref_and_no_name_is_found_by_its_route():
    snapshot = route_snapshot()

    assert [r.ref for r in snapshot.roads_named("INTERSTATE 89")] == ["way/2"]
    assert [r.ref for r in snapshot.roads_named("I-89")] == ["way/2"]
    assert snapshot.roads_named("ROUTE 89") == []


def test_a_ref_with_several_values_matches_each_of_them():
    snapshot = route_snapshot()

    assert {r.ref for r in snapshot.roads_named("US 4")} == {"way/5", "way/6"}
    assert {r.ref for r in snapshot.roads_named("NH 4A")} == {"way/5", "way/6"}
    assert {r.ref for r in snapshot.roads_named("ROUTE 4")} == {"way/5", "way/6"}


def test_a_way_named_for_its_route_matches_with_no_ref():
    snapshot = route_snapshot(
        [route_way(1, "State Route 120", None, (1, 43.65, -72.30), (2, 43.65, -72.25))]
    )

    assert [r.ref for r in snapshot.roads_named("RT 120")] == ["way/1"]


def test_a_name_still_matches_by_name():
    snapshot = route_snapshot()

    assert [r.ref for r in snapshot.roads_named("DARTMOUTH COLLEGE HWY")] == ["way/1"]
    assert [r.ref for r in snapshot.roads_named("HANOVER ST")] == ["way/3", "way/4"]


def test_a_crossing_on_route_120_is_found():
    match = locate_intersection(route_snapshot(), "ROUTE 120", "HANOVER ST")

    assert match is not None
    assert (match.lat, match.lng, match.osm_ref) == (43.65, -72.25, "node/2")


def test_a_crossing_on_interstate_89_is_found():
    match = locate_intersection(route_snapshot(), "I-89", "HANOVER ST")

    assert match is not None
    assert (match.lat, match.lng, match.osm_ref) == (43.64, -72.25, "node/11")


def test_a_place_on_route_120_gets_candidates():
    features = [
        feature("node", 1, 43.6502, -72.26, name="Sample Outlet Mall"),
        feature("node", 2, 43.70, -72.26, name="Sample Outlet Annex"),
    ]
    snapshot = snapshot_from_replies(
        "2026-11-23", {"elements": features}, {"elements": ROUTES}
    )

    found = place_candidates(snapshot, "Sample Outlet Mall", "ROUTE 120")

    # The annex is 5 km from the road, so only the mall is a candidate.
    assert [c.feature.ref for c in found] == ["node/1"]


def test_a_road_pin_is_the_middle_of_the_longest_way_and_approximate():
    match = locate_road(route_snapshot(), "ROUTE 4")

    # Long Road is the longer of the two ways that share the ref.
    assert match is not None
    assert (match.lat, match.lng, match.osm_ref) == (43.67, -72.24, "way/6")
    assert (match.precision, match.via) == ("approximate", "road")


def test_a_road_pin_is_found_from_words_around_the_route():
    match = locate_road(route_snapshot(), "ROCK CUT - ROUTE 120")

    assert match is not None and match.osm_ref == "way/1"


def test_a_road_that_is_not_in_the_snapshot_has_no_pin():
    assert locate_road(route_snapshot(), "ROUTE 9") is None
    assert locate_road(route_snapshot(), "Nowhere Rd") is None


def test_the_road_the_same_name_gets_when_it_is_named_not_numbered():
    match = locate_road(route_snapshot(), "Dartmouth College Highway")

    assert match is not None and match.osm_ref == "way/1"


def test_the_route_ref_survives_a_round_trip_through_json():
    original = route_snapshot()

    again = Snapshot.from_json(original.to_json())

    assert [r.route_ref for r in again.roads] == [r.route_ref for r in original.roads]
    assert [r.ref for r in again.roads_named("I-89")] == ["way/2"]


def test_a_snapshot_saved_before_routes_were_kept_still_loads():
    old = {
        "fetched_at": "2026-11-20",
        "features": [],
        "roads": [
            {
                "ref": "way/1",
                "name": "Hanover St",
                "nodes": [1, 2],
                "points": [[43.64, -72.25], [43.65, -72.25]],
            }
        ],
    }

    loaded = Snapshot.from_json(json.dumps(old))

    assert loaded.roads[0].route_ref == ""
    assert [r.ref for r in loaded.roads_named("HANOVER ST")] == ["way/1"]
    assert loaded.roads_named("ROUTE 120") == []


def test_a_way_with_neither_a_name_nor_a_ref_is_dropped():
    snapshot = route_snapshot(
        [route_way(1, None, None, (1, 43.6, -72.2), (2, 43.7, -72.2))]
    )

    assert snapshot.roads == []


# --- a road pin stays in town, and a bare route must be unambiguous ---


def test_a_road_that_runs_out_of_town_gets_a_point_inside_the_city():
    # The way starts in town and runs 10 km north past the city's edge.
    way_out = route_way(
        1,
        None,
        "I 89",
        (1, 43.60, -72.25),
        (2, 43.65, -72.25),
        (3, 43.69, -72.25),
        (4, 43.80, -72.25),
        (5, 43.90, -72.25),
    )

    match = locate_road(route_snapshot([way_out]), "I-89")

    assert match is not None
    assert in_city_bounds(match.lat, match.lng)
    assert match.lat <= 43.69


def test_a_road_wholly_out_of_town_has_no_point():
    way_out = route_way(1, None, "I 89", (1, 43.80, -72.25), (2, 43.90, -72.25))

    assert locate_road(route_snapshot([way_out]), "I-89") is None


def test_the_point_is_halfway_in_meters_not_in_vertices():
    # One long segment, then three vertices crowded at the north end. The middle vertex by
    # count is the second of the crowd, and the halfway point by distance is where the long
    # segment ends.
    ways = [
        route_way(
            1,
            "Crowded Road",
            None,
            (1, 43.600, -72.25),
            (2, 43.680, -72.25),
            (3, 43.681, -72.25),
            (4, 43.682, -72.25),
            (5, 43.683, -72.25),
        )
    ]

    match = locate_road(route_snapshot(ways), "Crowded Road")

    assert match is not None
    assert match.lat == 43.680


def test_a_bare_route_that_finds_both_a_state_and_a_federal_road_is_a_miss():
    ways = [
        route_way(1, "Maple Rd", "NH 9", (1, 43.60, -72.30), (2, 43.62, -72.30)),
        route_way(2, "Oak Rd", "US 9", (3, 43.64, -72.20), (4, 43.66, -72.20)),
    ]
    snapshot = route_snapshot(ways)

    assert snapshot.roads_named("ROUTE 9") == []
    assert locate_road(snapshot, "ROUTE 9") is None
    # A route that says which it is still matches.
    assert [r.ref for r in snapshot.roads_named("NH 9")] == ["way/1"]
    assert [r.ref for r in snapshot.roads_named("US 9")] == ["way/2"]


def test_a_bare_route_whose_two_refs_are_one_road_is_not_ambiguous():
    ways = [
        route_way(1, "Maple Rd", "NH 9;US 9", (1, 43.60, -72.30), (2, 43.62, -72.30))
    ]

    assert [r.ref for r in route_snapshot(ways).roads_named("ROUTE 9")] == ["way/1"]


def test_a_route_number_is_matched_with_its_letter():
    ways = [route_way(1, "Maple Rd", "NH 4A", (1, 43.60, -72.30), (2, 43.62, -72.30))]
    snapshot = route_snapshot(ways)

    assert snapshot.roads_named("ROUTE 4") == []
    assert [r.ref for r in snapshot.roads_named("ROUTE 4A")] == ["way/1"]


def test_a_snapshot_saved_with_a_null_name_loads():
    old = {
        "fetched_at": "2026-11-20",
        "features": [],
        "roads": [
            {
                "ref": "way/1",
                "name": None,
                "nodes": [1, 2],
                "points": [[43.64, -72.25], [43.65, -72.25]],
            }
        ],
    }

    loaded = Snapshot.from_json(json.dumps(old))

    assert loaded.roads[0].name == ""
    assert loaded.roads_named("HANOVER ST") == []


# --- is this the road that was asked for ---


@pytest.mark.parametrize(
    ("requested", "name", "ref"),
    [
        ("MAIN ST", "Main Street", None),
        ("ROUTE 120", "Dartmouth College Highway", "NH 120"),
        ("ROUTE 120", None, "NH 120;US 4"),
        ("RT 4", None, "NH 120;US 4"),
        ("I-89", None, "I 89"),
        ("INTERSTATE 89", "Interstate 89", None),
        ("US 4", "State Route 4", "US 4"),
        ("ROUTE 120", "State Route 120", None),
    ],
)
def test_a_road_with_the_same_name_or_route_is_the_road_asked_for(requested, name, ref):
    assert names_the_road(requested, name=name, ref=ref)


@pytest.mark.parametrize(
    ("requested", "name", "ref"),
    [
        ("I-89", "Hanover Street", None),
        ("ROUTE 120", "Hanover Street", "NH 10"),
        ("ROUTE 4", None, "NH 4A"),
        ("ROUTE 120", None, None),
        ("MAIN ST", None, None),
        ("ROUTE 89", None, "I 89"),
    ],
)
def test_another_road_or_an_answer_with_no_name_is_not_the_road_asked_for(
    requested, name, ref
):
    assert not names_the_road(requested, name=name, ref=ref)


def test_a_route_inside_other_words_is_found_only_when_asked():
    assert names_the_road("ROUTE I-89", name=None, ref="I 89", anywhere=True)
    assert not names_the_road("ROUTE I-89", name=None, ref="I 89")
