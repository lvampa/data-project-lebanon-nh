"""What the crossings backfill changes, as pure functions over plain rows.

A crossing spelled two ways, "Mechanic St and Poverty Ln" and "Poverty Ln and Mechanic St",
or "Lahaye" and "LaHaye", has two sets of rows and so two pins on one spot. The job now
stores every crossing in one spelling. This works out how to bring the rows already
stored to one, and the script in tmp/ writes the result. Nothing here reads a database.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from locations.canonical import canonical_crossing, crossing_key

PIN_FIELDS = (
    "lat",
    "lng",
    "coordinate_precision",
    "geocoded_via",
    "osm_ref",
    "geocode_source_url",
)


@dataclass(frozen=True)
class CrossingRow:
    id: int
    raw_address: str
    normalized_address: str
    source: str
    geocode_query: str | None
    # How many log entries the row's raw address covers, to find the most-used spelling.
    entries: int
    lat: float | None = None
    lng: float | None = None
    coordinate_precision: str | None = None
    geocoded_via: str | None = None
    osm_ref: str | None = None
    geocode_source_url: str | None = None

    def pin(self) -> tuple[object, ...]:
        return tuple(getattr(self, name) for name in PIN_FIELDS)


@dataclass(frozen=True)
class Rewrite:
    """One `ai` or `rule` row's new values, and the old ones that the CSV keeps."""

    row: CrossingRow
    normalized_address: str
    geocode_query: str
    pin: tuple[object, ...]

    @property
    def text_changed(self) -> bool:
        return self.normalized_address != self.row.normalized_address

    @property
    def pin_changed(self) -> bool:
        return self.pin != self.row.pin()


@dataclass
class Group:
    key: str
    target: str
    rewrites: list[Rewrite] = field(default_factory=list)
    # `human` rows are never rewritten. Their spelling and pin win, and they are listed.
    human: list[CrossingRow] = field(default_factory=list)


def plan_groups(rows: Iterable[CrossingRow]) -> list[Group]:
    """The groups whose rows need a change: a split spelling, an order that is not the
    stored order, or pins that differ."""
    by_key: dict[str, list[CrossingRow]] = defaultdict(list)
    for row in rows:
        key = crossing_key(row.normalized_address)
        if key is not None:
            by_key[key].append(row)

    groups = []
    for key, members in sorted(by_key.items()):
        if not _is_split(members):
            continue
        group = _plan_group(key, members)
        if any(r.text_changed or r.pin_changed for r in group.rewrites):
            groups.append(group)
    return groups


def _is_split(members: list[CrossingRow]) -> bool:
    """More than one spelling, or more than one pin. A crossing in one spelling with one pin
    is left as it is, even when its streets are not in alphabetical order: a new spelling
    of it takes the stored text, so it never splits."""
    spellings = {row.normalized_address for row in members}
    pins = {row.pin() for row in members if row.lat is not None}
    return len(spellings) > 1 or len(pins) > 1


def _plan_group(key: str, members: list[CrossingRow]) -> Group:
    humans = sorted((r for r in members if r.source == "human"), key=lambda r: r.id)
    target = _target(members, humans)
    pin = _best_pin(members, humans)
    group = Group(key=key, target=target, human=humans)
    for row in sorted(members, key=lambda r: r.id):
        if row.source == "human":
            continue
        group.rewrites.append(
            Rewrite(
                row=row,
                normalized_address=target,
                geocode_query=f"{target}, Lebanon, NH",
                pin=pin if pin is not None else row.pin(),
            )
        )
    return group


def _target(members: list[CrossingRow], humans: list[CrossingRow]) -> str:
    """A person's spelling when one has placed the crossing, as it was typed. Otherwise
    the most-used spelling, with its legs in order."""
    if humans:
        return humans[0].normalized_address
    spellings: dict[str, int] = defaultdict(int)
    for row in members:
        spellings[row.normalized_address] += row.entries
    # Most used first, then the first by text, so the choice does not move between runs.
    best = min(spellings, key=lambda text: (-spellings[text], text))
    return canonical_crossing(best)


def _best_pin(
    members: list[CrossingRow], humans: list[CrossingRow]
) -> tuple[object, ...] | None:
    """The pin every row of the group takes: a person's first, then an exact one, then the
    lowest id. None when no row has one of those, and then only the text changes.

    An approximate pin is never copied. These rows are all crossings, and a crossing takes
    only a point, never the point of a street, so an approximate pin is not one to spread.
    """
    placed = [
        r
        for r in members
        if r.lat is not None
        and r.lng is not None
        and (r in humans or r.coordinate_precision == "exact")
    ]
    if not placed:
        return None
    return min(placed, key=lambda row: (0 if row in humans else 1, row.id)).pin()
