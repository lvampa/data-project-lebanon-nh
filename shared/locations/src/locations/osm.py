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
from locations.geocode import in_city_bounds

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

Via = Literal["address", "intersection", "road", "llm"]


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
    # Empty for a way that has only a route number.
    name: str
    nodes: tuple[int, ...]
    points: tuple[tuple[float, float], ...]
    # The way's `ref` tag, such as "NH 120;US 4". Snapshots from before it was kept have none.
    route_ref: str = ""


@dataclass(frozen=True)
class Match:
    lat: float
    lng: float
    osm_ref: str
    via: Via
    name: str
    address: str
    precision: Literal["exact", "approximate"] = "exact"


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
        self._roads_by_route: dict[str, list[Road]] = {}
        for feature in features:
            if feature.housenumber and feature.street:
                key = (_house_key(feature.housenumber), street_key(feature.street))
                self._by_address.setdefault(key, []).append(feature)
            for token in _tokens(feature.name or ""):
                self._by_token.setdefault(token, []).append(feature)
        for road in roads:
            if road.name:
                self._roads_by_street.setdefault(street_key(road.name), []).append(road)
            for route in _routes_of(road):
                self._roads_by_route.setdefault(route, []).append(road)

    def features_at(self, housenumber: str, street: str) -> list[Feature]:
        return self._by_address.get((_house_key(housenumber), street_key(street)), [])

    def features_named(self, token: str) -> list[Feature]:
        return self._by_token.get(token, [])

    def roads_named(self, street: str) -> list[Road]:
        """The ways named `street`, and the ways whose route number it is, as "ROUTE 120"
        is for a way with `ref` "NH 120"."""
        return self._roads_matching(street, anywhere=False)

    def roads_in(self, text: str) -> list[Road]:
        """Like `roads_named`, but finds a route number anywhere in the text, as in
        "ROCK CUT - ROUTE 120"."""
        return self._roads_matching(text, anywhere=True)

    def _roads_matching(self, text: str, *, anywhere: bool) -> list[Road]:
        found = {
            road.ref: road for road in self._roads_by_street.get(street_key(text), [])
        }
        for alternatives in _route_alternatives(text, anywhere=anywhere):
            by_route = [
                self._roads_by_route[route]
                for route in sorted(alternatives)
                if route in self._roads_by_route
            ]
            if (
                len(by_route) > 1
                and len({tuple(r.ref for r in roads) for roads in by_route}) > 1
            ):
                # A bare "ROUTE 4" that finds both a state and a federal road does not say
                # which one, so it matches neither.
                continue
            for roads in by_route:
                for road in roads:
                    found.setdefault(road.ref, road)
        return list(found.values())

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
                    r["name"] or "",
                    tuple(r["nodes"]),
                    tuple((p[0], p[1]) for p in r["points"]),
                    r.get("route_ref", ""),
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
    tags = element.get("tags") or {}
    name = tags.get("name") or ""
    route_ref = tags.get("ref") or ""
    nodes = element.get("nodes") or []
    geometry = element.get("geometry") or []
    if element.get("type") != "way" or not (name or route_ref):
        return None
    if len(nodes) != len(geometry):
        return None
    if any(point is None for point in geometry):
        return None
    return Road(
        ref=f"way/{element['id']}",
        name=name,
        nodes=tuple(nodes),
        points=tuple((float(p["lat"]), float(p["lon"])) for p in geometry),
        route_ref=route_ref,
    )


# A route number as the log writes it, and as OpenStreetMap writes `ref`. The text is upper
# case, with dots dropped and hyphens as spaces, so "I-89" is "I 89" and "U.S. 4" is "US 4".
_ROUTE = re.compile(
    r"(?<![A-Z0-9])"
    r"(?P<prefix>INTERSTATE|NEW HAMPSHIRE ROUTE|STATE ROUTE|STATE RTE|STATE RT|STATE HWY"
    r"|US ROUTE|US HIGHWAY|US HWY|NH ROUTE|NH RTE|NH RT|NH HWY|ROUTE|HIGHWAY|RTE|RT|HWY"
    r"|US|U S|NH|I)"
    r"\s*(?P<number>\d{1,3}[A-Z]?)(?![A-Z0-9])"
)


def route_refs(text: str, *, anywhere: bool = False) -> set[str]:
    """The `ref` values a road called `text` can have: "ROUTE 120" is "NH 120" or "US 120",
    "I-89" is "I 89", "US 4" is "US 4". A bare "ROUTE", "RT" or "HWY" can be a state or a
    federal route, never an interstate. With `anywhere`, the route number may sit inside
    other words, as in "ROCK CUT - ROUTE 120". Otherwise the text must be only the route.
    The number is a whole token with its letter, so "4" never matches "4A".
    """
    return {
        ref
        for alternatives in _route_alternatives(text, anywhere=anywhere)
        for ref in alternatives
    }


def _route_alternatives(text: str, *, anywhere: bool) -> list[tuple[str, ...]]:
    """One tuple per route in the text. A bare route has two refs to choose between."""
    cleaned = " ".join(text.upper().replace(".", "").replace("-", " ").split())
    matches = (
        list(_ROUTE.finditer(cleaned))
        if anywhere
        else [m for m in [_ROUTE.fullmatch(cleaned)] if m is not None]
    )
    alternatives: list[tuple[str, ...]] = []
    for match in matches:
        prefix, number = match["prefix"], match["number"]
        if prefix in ("I", "INTERSTATE"):
            alternatives.append((f"I {number}",))
        elif prefix.startswith(("US", "U S")):
            alternatives.append((f"US {number}",))
        elif prefix.startswith(("NH", "NEW HAMPSHIRE", "STATE")):
            alternatives.append((f"NH {number}",))
        else:
            alternatives.append((f"NH {number}", f"US {number}"))
    return alternatives


def _routes_of(road: Road) -> set[str]:
    """Every route number a way has: its `ref` values, and the one its name spells out."""
    routes = {ref for value in road.route_ref.split(";") for ref in _ref_values(value)}
    if road.name:
        routes |= route_refs(road.name)
    return routes


def _ref_values(value: str) -> set[str]:
    cleaned = " ".join(value.upper().replace(".", "").replace("-", " ").split())
    return route_refs(cleaned) or ({cleaned} if cleaned else set())


def locate_road(snapshot: Snapshot, text: str) -> Match | None:
    """A point on the road a highway row names, or None.

    A road is often many ways, and a point on it is only somewhere along it, so the match is
    approximate. It is the point halfway along the longest way, measured in meters along the
    part of the way inside the city, which does not move between runs. A way is fetched
    whole, so one that runs out of town, as I-89 does, is cut at the city's edge first.
    """
    parts = [
        (road, inside)
        for road in snapshot.roads_in(text)
        if (inside := [p for p in road.points if in_city_bounds(*p)])
    ]
    if not parts:
        return None
    road, inside = max(parts, key=lambda part: (_length(part[1]), part[0].ref))
    lat, lng = _halfway(inside)
    if not in_city_bounds(lat, lng):
        return None
    name = road.name or road.route_ref
    return Match(lat, lng, road.ref, "road", name, "", precision="approximate")


def _length(points: list[tuple[float, float]]) -> float:
    return sum(
        meters_between(a[0], a[1], b[0], b[1])
        for a, b in zip(points, points[1:], strict=False)
    )


def _halfway(points: list[tuple[float, float]]) -> tuple[float, float]:
    """The vertex nearest the halfway point along the line, in meters, not in vertices.

    The points are the ones inside the city. A way that leaves the box and comes back has a
    gap between two of them, and the length counts the jump across it. That is harmless: all
    this needs is a point that does not move between runs.
    """
    half = _length(points) / 2
    best, best_gap, walked = points[0], abs(half), 0.0
    for a, b in zip(points, points[1:], strict=False):
        walked += meters_between(a[0], a[1], b[0], b[1])
        if abs(walked - half) < best_gap:
            best, best_gap = b, abs(walked - half)
    return best


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
