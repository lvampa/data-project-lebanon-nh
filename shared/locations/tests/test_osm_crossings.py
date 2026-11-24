"""Crossings with no shared node, highway points and exits, on invented geometry.

One degree of latitude is about 110 km here, so 0.0001 is about 11 m, and a degree of
longitude near 43.65 N is about 80 km, so 0.0001 is about 8 m.
"""

import pytest
from locations.osm import (
    Snapshot,
    locate_highway_point,
    locate_intersection,
    meters_between,
    snapshot_from_replies,
)


def way(way_id: int, tags: dict[str, str], *points: tuple[int, float, float]) -> dict:
    return {
        "type": "way",
        "id": way_id,
        "tags": tags,
        "nodes": [node for node, _, _ in points],
        "geometry": [{"lat": lat, "lon": lng} for _, lat, lng in points],
    }


def road(way_id: int, name: str, *points: tuple[int, float, float]) -> dict:
    return way(way_id, {"highway": "residential", "name": name}, *points)


def junction(node_id: int, exit_number: str, lat: float, lng: float) -> dict:
    return {
        "type": "node",
        "id": node_id,
        "lat": lat,
        "lon": lng,
        "tags": {"highway": "motorway_junction", "ref": exit_number},
    }


def snapshot(ways: list[dict], junctions: list[dict] | None = None) -> Snapshot:
    return snapshot_from_replies(
        "2026-11-23",
        {"elements": []},
        {"elements": ways},
        {"elements": junctions or []},
    )


def interstate(way_id: int, *points: tuple[int, float, float]) -> dict:
    return way(way_id, {"highway": "motorway", "ref": "I 89"}, *points)


EAST_WEST = road(1, "Sample Rd", (1, 43.6500, -72.2600), (2, 43.6500, -72.2400))


def test_roads_that_cross_with_no_shared_node_meet_where_they_cross():
    overpass = road(2, "Example Ave", (3, 43.6490, -72.2500), (4, 43.6510, -72.2500))

    match = locate_intersection(
        snapshot([EAST_WEST, overpass]), "Sample Rd", "Example Ave"
    )

    assert match is not None
    assert (match.via, match.precision) == ("intersection", "exact")
    assert meters_between(match.lat, match.lng, 43.6500, -72.2500) < 1
    assert match.osm_ref == "way/1+way/2"


def test_roads_that_pass_within_100_m_meet_at_the_middle_of_the_gap():
    # The second road ends 33 m south of the first, with no node in common.
    near = road(2, "Example Ave", (3, 43.6470, -72.2500), (4, 43.6497, -72.2500))

    match = locate_intersection(snapshot([EAST_WEST, near]), "Sample Rd", "Example Ave")

    assert match is not None
    assert meters_between(match.lat, match.lng, 43.64985, -72.2500) < 1


def test_roads_that_pass_120_m_apart_do_not_meet():
    far = road(2, "Example Ave", (3, 43.6470, -72.2500), (4, 43.6489, -72.2500))

    assert (
        locate_intersection(snapshot([EAST_WEST, far]), "Sample Rd", "Example Ave")
        is None
    )


def test_two_long_parallel_roads_50_m_apart_do_not_meet():
    parallel = road(2, "Example Ave", (3, 43.65045, -72.2600), (4, 43.65045, -72.2400))

    assert (
        locate_intersection(snapshot([EAST_WEST, parallel]), "Sample Rd", "Example Ave")
        is None
    )


def test_two_parallel_roads_with_many_vertices_do_not_meet():
    many = [(100 + n, 43.6500, -72.2600 + n * 0.0015) for n in range(14)]
    beside = [(200 + n, 43.65045, -72.2600 + n * 0.0015) for n in range(14)]

    found = locate_intersection(
        snapshot([road(1, "Sample Rd", *many), road(2, "Example Ave", *beside)]),
        "Sample Rd",
        "Example Ave",
    )

    assert found is None


def test_roads_that_cross_in_two_places_far_apart_do_not_meet():
    bent = road(
        2,
        "Example Ave",
        (3, 43.6490, -72.2500),
        (4, 43.6510, -72.2500),
        (5, 43.6510, -72.2400),
        (6, 43.6490, -72.2400),
    )

    assert (
        locate_intersection(snapshot([EAST_WEST, bent]), "Sample Rd", "Example Ave")
        is None
    )


def test_the_two_carriageways_of_a_divided_road_are_one_crossing():
    divided = [
        road(1, "Sample Rd", (1, 43.6500, -72.2600), (2, 43.6500, -72.2400)),
        road(3, "Sample Rd", (5, 43.6503, -72.2600), (6, 43.6503, -72.2400)),
    ]
    cross = road(2, "Example Ave", (3, 43.6490, -72.2500), (4, 43.6510, -72.2500))

    match = locate_intersection(snapshot([*divided, cross]), "Sample Rd", "Example Ave")

    assert match is not None
    assert meters_between(match.lat, match.lng, 43.65015, -72.2500) < 2


def test_a_shared_node_still_wins_over_a_geometric_crossing():
    meets = road(2, "Example Ave", (2, 43.6500, -72.2400), (4, 43.6520, -72.2400))

    match = locate_intersection(
        snapshot([EAST_WEST, meets]), "Sample Rd", "Example Ave"
    )

    assert match is not None
    assert match.osm_ref == "node/2"


def test_a_snapshot_saved_before_exits_still_loads_and_crosses():
    overpass = road(2, "Example Ave", (3, 43.6490, -72.2500), (4, 43.6510, -72.2500))
    saved = snapshot([EAST_WEST, overpass]).to_json()
    import json

    old = json.loads(saved)
    del old["junctions"]
    for each in old["roads"]:
        del each["highway"]

    loaded = Snapshot.from_json(json.dumps(old))

    assert loaded.junctions == []
    assert locate_intersection(loaded, "Sample Rd", "Example Ave") is not None


def test_the_snapshot_keeps_junctions_and_the_highway_tag():
    built = snapshot(
        [interstate(5, (10, 43.6500, -72.2000), (11, 43.6520, -72.2100))],
        [junction(11, "17", 43.6520, -72.2100)],
    )

    again = Snapshot.from_json(built.to_json())

    assert [(j.ref, j.exit) for j in again.junctions] == [("node/11", "17")]
    assert again.roads[0].highway == "motorway"


# --- highway points ---

# Northbound runs west here, so its nodes have falling longitude. The southbound way's
# have rising longitude, 20 m to the south.
NORTHBOUND = interstate(
    10, (20, 43.6500, -72.2000), (21, 43.6510, -72.2100), (22, 43.6520, -72.2200)
)
SOUTHBOUND = interstate(
    11, (30, 43.6518, -72.2200), (31, 43.6508, -72.2100), (32, 43.6498, -72.2000)
)
EXITS = [junction(21, "17", 43.6510, -72.2100), junction(31, "17", 43.6508, -72.2100)]
CROSSING_ROAD = road(
    12, "Example Ave", (40, 43.6560, -72.2150), (41, 43.6490, -72.2150)
)


def highway_snapshot() -> Snapshot:
    return snapshot([NORTHBOUND, SOUTHBOUND, CROSSING_ROAD], EXITS)


def test_an_exit_is_its_junction_node():
    match = locate_highway_point(highway_snapshot(), "I-89 near Exit 17")

    assert match is not None
    assert (match.via, match.precision) == ("road", "exact")
    assert meters_between(match.lat, match.lng, 43.6509, -72.2100) < 1


def test_an_exit_with_a_direction_takes_that_carriageway():
    north = locate_highway_point(highway_snapshot(), "I-89 northbound near Exit 17")
    south = locate_highway_point(highway_snapshot(), "I-89 southbound near Exit 17")

    assert north is not None and south is not None
    assert north.osm_ref == "node/21"
    assert south.osm_ref == "node/31"


def test_an_exit_with_sb_after_it_takes_the_southbound_carriageway():
    match = locate_highway_point(highway_snapshot(), "I-89 at Exit 17 SB")

    assert match is not None
    assert match.osm_ref == "node/31"


def test_an_exit_the_snapshot_does_not_have_is_a_miss_with_no_road_named():
    assert locate_highway_point(highway_snapshot(), "I-89 near Exit 15") is None


def test_two_exits_name_no_one_point():
    snap = highway_snapshot()

    assert locate_highway_point(snap, "I-89 northbound between exits 17 and 18") is None
    assert locate_highway_point(snap, "I-89 near Exit 17 toward Exit 18") is None


def test_a_highway_near_a_road_is_where_they_cross():
    match = locate_highway_point(highway_snapshot(), "I-89 near Example Ave")

    assert match is not None
    assert match.via == "intersection"
    assert meters_between(match.lat, match.lng, 43.6514, -72.2150) < 400


@pytest.mark.parametrize(
    "text",
    [
        "I-89 at Example Ave interchange",
        "I-89 at Example Ave, Exit 15",
        "I-89 northbound on-ramp at Example Ave",
    ],
)
def test_the_words_around_the_road_are_ignored(text):
    match = locate_highway_point(highway_snapshot(), text)

    assert match is not None
    assert match.via == "intersection"


def test_a_mile_marker_alone_is_a_miss():
    assert (
        locate_highway_point(
            highway_snapshot(), "I-89 northbound near mile marker 57.2"
        )
        is None
    )


def test_an_exit_with_a_mile_marker_is_placed_by_the_exit():
    match = locate_highway_point(
        highway_snapshot(), "I-89 northbound near mile marker 54.8, Exit 17"
    )

    assert match is not None
    assert match.osm_ref == "node/21"


def test_with_no_junctions_in_the_snapshot_an_exit_falls_back_to_the_road_named():
    snap = snapshot([NORTHBOUND, SOUTHBOUND, CROSSING_ROAD])

    assert locate_highway_point(snap, "I-89 near Exit 17") is None
    assert locate_highway_point(snap, "I-89 at Example Ave, Exit 17") is not None
