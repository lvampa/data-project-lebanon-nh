"""Find a Lebanon, NH location in a saved OpenStreetMap snapshot.

The snapshot is two Overpass downloads kept in one file: every named or numbered
feature in the city, and every named road with its nodes. The functions here are pure,
with no network and no database, so every rule can be tested with a small fixture.

OpenStreetMap spells street names out ("Mount Support Road"). `canonical_address` maps
both that and the log's "MT SUPPORT RD" to one form, so streets are compared in that
form and there is no second spelling table.
"""

import json
import math
import re
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal

from locations.canonical import canonical_address

# Nodes of two roads this close together are one crossing, such as a divided road's.
INTERSECTION_SPREAD_M = 150
# A feature this close to its street, or closer, can be a place on it.
STREET_REACH_M = 200
# Features with one house number and street this close are one building's parts.
SAME_BUILDING_M = 10
SNAPSHOT_GLOB = "snapshot-*.json"

# Words a place name shares with many places, which say nothing about which one it is.
_STOP_TOKENS = frozenset(
    [
        "the",
        "at",
        "of",
        "and",
        "building",
        "bldg",
        "apartments",
        "apts",
        "center",
        "store",
        "shop",
        "inc",
        "llc",
        "lot",
        "unit",
    ]
)
_TOKEN = re.compile(r"[a-z0-9]+")
_FEATURE_KINDS = (
    "amenity",
    "shop",
    "tourism",
    "leisure",
    "office",
    "healthcare",
    "building",
)

Via = Literal["address", "intersection", "llm"]


@dataclass(frozen=True)
class Feature:
    ref: str
    name: str | None
    housenumber: str | None
    street: str | None
    kind: str
    building: bool
    lat: float
    lng: float

    @property
    def address(self) -> str:
        return " ".join(part for part in (self.housenumber, self.street) if part)


@dataclass(frozen=True)
class Road:
    ref: str
    name: str
    nodes: tuple[int, ...]
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class Match:
    lat: float
    lng: float
    osm_ref: str
    via: Via
    name: str
    address: str


@dataclass(frozen=True)
class Candidate:
    feature: Feature
    meters_from_street: float
    score: float


class Snapshot:
    def __init__(
        self, fetched_at: str, features: list[Feature], roads: list[Road]
    ) -> None:
        self.fetched_at = fetched_at
        self.features = features
        self.roads = roads
        self._by_address: dict[tuple[str, str], list[Feature]] = {}
        self._by_token: dict[str, list[Feature]] = {}
        self._roads_by_street: dict[str, list[Road]] = {}
        for feature in features:
            if feature.housenumber and feature.street:
                key = (_house_key(feature.housenumber), street_key(feature.street))
                self._by_address.setdefault(key, []).append(feature)
            for token in _tokens(feature.name or ""):
                self._by_token.setdefault(token, []).append(feature)
        for road in roads:
            self._roads_by_street.setdefault(street_key(road.name), []).append(road)

    def features_at(self, housenumber: str, street: str) -> list[Feature]:
        return self._by_address.get((_house_key(housenumber), street_key(street)), [])

    def features_named(self, token: str) -> list[Feature]:
        return self._by_token.get(token, [])

    def roads_named(self, street: str) -> list[Road]:
        return self._roads_by_street.get(street_key(street), [])

    def to_json(self) -> str:
        return json.dumps(
            {
                "fetched_at": self.fetched_at,
                "features": [asdict(f) for f in self.features],
                "roads": [asdict(r) for r in self.roads],
            }
        )

    @classmethod
    def from_json(cls, text: str) -> "Snapshot":
        data = json.loads(text)
        return cls(
            data["fetched_at"],
            [Feature(**f) for f in data["features"]],
            [
                Road(
                    r["ref"],
                    r["name"],
                    tuple(r["nodes"]),
                    tuple((p[0], p[1]) for p in r["points"]),
                )
                for r in data["roads"]
            ],
        )

    @classmethod
    def load_newest(cls, directory: Path) -> "Snapshot":
        files = sorted(directory.glob(SNAPSHOT_GLOB))
        if not files:
            raise FileNotFoundError(
                f"No OpenStreetMap snapshot in {directory}. Run `uv run osm-snapshot`."
            )
        return cls.from_json(files[-1].read_text())


def street_key(street: str) -> str:
    return canonical_address(street)


def snapshot_from_replies(
    fetched_at: str, features_reply: dict[str, Any], roads_reply: dict[str, Any]
) -> Snapshot:
    features = [
        f for f in map(_feature_of, features_reply["elements"]) if f is not None
    ]
    roads = [r for r in map(_road_of, roads_reply["elements"]) if r is not None]
    return Snapshot(fetched_at, features, roads)


def _feature_of(element: dict[str, Any]) -> Feature | None:
    tags = element.get("tags") or {}
    where = element if "lat" in element else element.get("center")
    if not where or not (tags.get("name") or tags.get("addr:housenumber")):
        return None
    kind = next((f"{key}={tags[key]}" for key in _FEATURE_KINDS if key in tags), "")
    return Feature(
        ref=f"{element['type']}/{element['id']}",
        name=tags.get("name"),
        housenumber=tags.get("addr:housenumber"),
        street=tags.get("addr:street"),
        kind=kind,
        building="building" in tags,
        lat=float(where["lat"]),
        lng=float(where["lon"]),
    )


def _road_of(element: dict[str, Any]) -> Road | None:
    name = (element.get("tags") or {}).get("name")
    nodes = element.get("nodes") or []
    geometry = element.get("geometry") or []
    if element.get("type") != "way" or not name or len(nodes) != len(geometry):
        return None
    if any(point is None for point in geometry):
        return None
    return Road(
        ref=f"way/{element['id']}",
        name=name,
        nodes=tuple(nodes),
        points=tuple((float(p["lat"]), float(p["lon"])) for p in geometry),
    )


def locate_address(snapshot: Snapshot, housenumber: str, street: str) -> Match | None:
    """The one building with this house number on this street, or None.

    Several features with the same number and street are parts of one building when they
    lie within 10 m, and then the pin is their centroid. Otherwise it is a miss, since
    guessing between two buildings puts the pin on the wrong one.
    """
    found = snapshot.features_at(housenumber, street)
    buildings = [f for f in found if f.building] or found
    if not buildings:
        return None
    first = buildings[0]
    if any(
        meters_between(first.lat, first.lng, f.lat, f.lng) > SAME_BUILDING_M
        for f in buildings
    ):
        return None
    lat = sum(f.lat for f in buildings) / len(buildings)
    lng = sum(f.lng for f in buildings) / len(buildings)
    return Match(lat, lng, first.ref, "address", first.name or "", first.address)


def locate_intersection(
    snapshot: Snapshot, street_a: str, street_b: str
) -> Match | None:
    """A node that a road named `street_a` and a road named `street_b` share.

    Several shared nodes within 150 m, as a divided road gives, are one crossing, and the
    pin is their centroid. Nodes farther apart mean the two streets cross in more than
    one place, which is a miss.
    """
    nodes_a = _node_points(snapshot.roads_named(street_a))
    nodes_b = _node_points(snapshot.roads_named(street_b))
    shared = nodes_a.keys() & nodes_b.keys()
    if not shared:
        return None
    points = [nodes_a[node] for node in shared]
    spread = max(meters_between(*p, *q) for p in points for q in points)
    if spread > INTERSECTION_SPREAD_M:
        return None
    lat = sum(p[0] for p in points) / len(points)
    lng = sum(p[1] for p in points) / len(points)
    return Match(
        lat,
        lng,
        f"node/{min(shared)}",
        "intersection",
        f"{street_a} and {street_b}",
        "",
    )


def place_candidates(
    snapshot: Snapshot, name: str, street: str, limit: int = 8
) -> list[Candidate]:
    """Features that could be the place the log calls `name` on `street`, best first.

    A feature must share a meaningful word with the name and lie within 200 m of the
    street. The distance holds for every candidate, so a same-named feature in another
    town, or across the river, never reaches the model.
    """
    roads = snapshot.roads_named(street)
    wanted = _tokens(name)
    if not roads or not wanted:
        return []
    key = street_key(street)
    seen: dict[str, Feature] = {}
    for token in wanted:
        for feature in snapshot.features_named(token):
            seen[feature.ref] = feature
    candidates = []
    for feature in seen.values():
        distance = min(
            _meters_to_road(feature.lat, feature.lng, road) for road in roads
        )
        if distance > STREET_REACH_M:
            continue
        on_street = feature.street is not None and street_key(feature.street) == key
        score = _name_score(name, feature.name or "") + (0.1 if on_street else 0.0)
        candidates.append(Candidate(feature, round(distance), score))
    candidates.sort(key=lambda c: (-c.score, c.meters_from_street, c.feature.ref))
    return candidates[:limit]


def _name_score(wanted: str, found: str) -> float:
    a, b = set(_tokens(wanted)), set(_tokens(found))
    jaccard = len(a & b) / len(a | b) if a | b else 0.0
    return jaccard + 0.5 * SequenceMatcher(None, wanted.lower(), found.lower()).ratio()


def _tokens(text: str) -> list[str]:
    return [
        t for t in _TOKEN.findall(text.lower()) if t not in _STOP_TOKENS and len(t) > 1
    ]


def _house_key(housenumber: str) -> str:
    return housenumber.upper().replace(" ", "")


def _node_points(roads: list[Road]) -> dict[int, tuple[float, float]]:
    return {
        n: p for road in roads for n, p in zip(road.nodes, road.points, strict=True)
    }


def meters_between(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Meters between two points, flat-earth, which is exact enough inside one city."""
    dy = (lat2 - lat1) * 110_540
    dx = (lng2 - lng1) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def _meters_to_road(lat: float, lng: float, road: Road) -> float:
    """The distance from a point to the nearest part of a road, segments included."""
    best = math.inf
    for (lat1, lng1), (lat2, lng2) in zip(road.points, road.points[1:], strict=False):
        best = min(best, _meters_to_segment(lat, lng, lat1, lng1, lat2, lng2))
    if len(road.points) == 1:
        best = meters_between(lat, lng, *road.points[0])
    return best


def _meters_to_segment(
    lat: float, lng: float, lat1: float, lng1: float, lat2: float, lng2: float
) -> float:
    cos = math.cos(math.radians(lat))
    px, py = (lng - lng1) * 111_320 * cos, (lat - lat1) * 110_540
    sx, sy = (lng2 - lng1) * 111_320 * cos, (lat2 - lat1) * 110_540
    length_sq = sx * sx + sy * sy
    t = 0.0 if length_sq == 0 else max(0.0, min(1.0, (px * sx + py * sy) / length_sq))
    return math.hypot(px - t * sx, py - t * sy)
