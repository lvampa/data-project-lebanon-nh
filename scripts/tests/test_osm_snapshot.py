from datetime import date

import pytest
from locations.osm import Snapshot
from locations.overpass import (
    FEATURES_QUERY,
    JUNCTIONS_QUERY,
    ROADS_QUERY,
    OverpassUnavailable,
)

from scripts.normalize.osm_snapshot import build_snapshot, main, write_snapshot

NH_BRIDGE = {
    "type": "way",
    "id": 1,
    "tags": {"highway": "residential", "name": "Bridge Street"},
    "nodes": [1, 2],
    "geometry": [{"lat": 43.64, "lon": -72.25}, {"lat": 43.641, "lon": -72.25}],
}
# White River Junction is inside the city box, and has a Bridge Street of its own.
VT_BRIDGE = {
    "type": "way",
    "id": 2,
    "tags": {"highway": "residential", "name": "Bridge Street"},
    "nodes": [8, 9],
    "geometry": [{"lat": 43.649, "lon": -72.319}, {"lat": 43.650, "lon": -72.319}],
}
NH_SHOP = {
    "type": "node",
    "id": 5,
    "lat": 43.64,
    "lon": -72.25,
    "tags": {"name": "Shop"},
}
VT_SHOP = {
    "type": "node",
    "id": 6,
    "lat": 43.649,
    "lon": -72.319,
    "tags": {"name": "Shop"},
}


def overpass(query: str) -> dict:
    """Overpass as it behaves: with the city area in the query, only New Hampshire comes
    back. Without it, the whole box does, Vermont included."""
    scoped = "area.city" in query
    if query == JUNCTIONS_QUERY:
        return {"elements": []}
    if query == ROADS_QUERY or "way(area" in query or "way[" in query:
        return {"elements": [NH_BRIDGE] if scoped else [NH_BRIDGE, VT_BRIDGE]}
    return {"elements": [NH_SHOP] if scoped else [NH_SHOP, VT_SHOP]}


def test_the_snapshot_holds_only_new_hampshire_features_and_roads():
    snapshot = build_snapshot(date(2026, 11, 20), overpass)

    assert [f.ref for f in snapshot.features] == ["node/5"]
    assert [r.ref for r in snapshot.roads] == ["way/1"]


def test_the_queries_it_sends_are_the_scoped_ones():
    sent: list[str] = []

    def record(query: str) -> dict:
        sent.append(query)
        return overpass(query)

    build_snapshot(date(2026, 11, 20), record)

    assert sent == [FEATURES_QUERY, ROADS_QUERY, JUNCTIONS_QUERY]


def test_an_empty_answer_is_an_error_not_an_empty_snapshot():
    with pytest.raises(OverpassUnavailable, match="boundary"):
        build_snapshot(date(2026, 11, 20), lambda query: {"elements": []})


def test_it_writes_a_dated_file_the_loader_finds(tmp_path):
    path = write_snapshot(build_snapshot(date(2026, 11, 20), overpass), tmp_path)

    assert path.name == f"snapshot-{date(2026, 11, 20).isoformat()}.json"
    assert Snapshot.load_newest(tmp_path).fetched_at == "2026-11-20"


def test_main_writes_the_file_and_says_so(tmp_path, capsys):
    assert main(["--dir", str(tmp_path)], query=overpass) == 0

    assert "1 features, 1 roads" in capsys.readouterr().out
    assert len(list(tmp_path.glob("snapshot-*.json"))) == 1


def test_main_fails_clearly_when_overpass_does(tmp_path, capsys):
    def down(query: str) -> dict:
        raise OverpassUnavailable("Overpass kept failing after 4 retries: HTTP 502.")

    assert main(["--dir", str(tmp_path)], query=down) == 1

    assert "HTTP 502" in capsys.readouterr().err
    assert list(tmp_path.glob("snapshot-*.json")) == []
