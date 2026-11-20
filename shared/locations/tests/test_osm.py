import pytest
from locations.osm import (
    Snapshot,
    locate_address,
    locate_intersection,
    place_candidates,
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
