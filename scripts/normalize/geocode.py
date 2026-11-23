"""Put normalized locations on the map, by hand from Connor's Mac.

    uv run geocode [--retry-approximate | --retry-missed] [--no-llm]

It takes `ai` and `rule` rows that have a normalized address and no coordinates, and
never a `human` row. It reuses the coordinates of a place code another row already
has, or the coordinates of another spelling of the same address. Otherwise it asks the
geocoder for the row's query, then looks the row up in the newest OpenStreetMap
snapshot (`uv run osm-snapshot`), then asks the geocoder for its street alone, and
drops a result outside the city. An intersection takes only a point, never a street's.
A row that misses three times is marked for review.
It stops after 600 requests, and leaves the rest for the next run.

From the snapshot, a house address is matched by number and street, an intersection by
a node its two roads share, and a named place by the AI choosing one of a few real
features near its street, or none. `--no-llm` leaves the last step out, and the AI is
called at most 100 times a run. Every placement from the snapshot goes in a file in
tmp/, with the old coordinates beside the new ones.

`--retry-approximate` looks again, from the snapshot only, at every row that sits on a
street point, a group of rows at a time. A miss changes nothing, and a group with a
`human` row in it is left alone.

`--retry-missed` does the same for rows with no point that the job marked for review:
three misses, or a bare highway that had no road. A hit places the row and resets its
attempts, and leaves the review mark, which normalize sets too. A miss changes nothing.

A bare highway, one that names no exit and no cross street, gets an approximate point on
the road the snapshot matches by name or by route number, and is marked for review only
when none matches.

A row whose lookup times out, cannot connect or gets a 5xx is skipped and not charged
an attempt, so the next run tries it again. A 403 or 429 stops the run at once, and so
do 5 skipped rows in a row. The exit code stays 0 when rows were only skipped, and the
summary says how many.
"""

import argparse
import re
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import logfire
from bootstrap import bootstrap
from locations.geocode import (
    GeocodeBackOff,
    GeocodeResult,
    GeocodeUnavailable,
    geocode,
    in_city_bounds,
)
from locations.osm import Candidate, Match, Snapshot, names_the_road
from mongo.ai_calls import AiCallLog, ai_calls_collection
from mongo.client import get_db
from postgres import get_engine, open_session
from postgres.lock import GEOCODE, advisory_lock
from postgres.models.address_normalization import AddressNormalization
from postgres.models.log_entry import LogEntry
from pydantic import ValidationError
from pymongo.errors import PyMongoError
from sqlalchemy import ColumnElement, func, or_, select, tuple_
from sqlalchemy.orm import Session

from scripts.normalize.backends import AiBackend, AiBackendUnavailable, backend_from_env
from scripts.normalize.match_review import DEFAULT_DIR as REVIEW_DIR
from scripts.normalize.match_review import Placed, write_review
from scripts.normalize.osm_locate import OsmLocator
from scripts.normalize.place_match import pick_candidate

MAX_ATTEMPTS = 3
MAX_REQUESTS = 600
# Rows in a row that fail with a timeout, a connection error or a 5xx before the run
# assumes the service, or our network, is down.
MAX_CONSECUTIVE_FAILURES = 5
PROGRESS_EVERY = 50

Geocoder = Callable[[str], GeocodeResult | None]

DEFAULT_SNAPSHOT_DIR = Path(__file__).parents[1] / "data" / "osm"

# A highway names a point when it gives a cross street, an exit, a mile marker, a rest area,
# a road it passes over or under, or a landmark. The last is a guess: anything that says
# "near" or "at".
_NAMES_A_POINT = re.compile(
    r"\b(and|exits?|near|at|over|under|mile\s*post|mile\s+marker|rest\s+area|mm\s*\d+)\b|&",
    re.IGNORECASE,
)


@dataclass
class GeocodeCounts:
    placed: int = 0
    reused: int = 0
    missed: int = 0
    bare_highways: int = 0
    requests: int = 0
    # Rows that timed out or could not connect, left for the next run.
    skipped: int = 0
    stopped_at_limit: bool = False
    geocoder_unavailable: bool = False
    # Why the geocoder stopped the run, as the geocoder worded it.
    geocoder_error: str = ""
    # What the snapshot placed, for the review file.
    from_snapshot: list[Placed] = field(default_factory=list)
    # Groups of rows `--retry-approximate` looked at, and left as they were.
    groups_retried: int = 0
    groups_kept: int = 0

    def found_by(self) -> Counter[str]:
        return Counter(item.match.via for item in self.from_snapshot)


@dataclass(frozen=True)
class Placement:
    lat: float
    lng: float
    precision: str
    via: str
    osm_ref: str | None = None
    match: Match | None = None


def run(
    geocoder: Geocoder = geocode,
    *,
    max_requests: int = MAX_REQUESTS,
    locator: OsmLocator | None = None,
) -> GeocodeCounts:
    counts = GeocodeCounts()
    with open_session() as session:
        rows = _rows_to_place(session)
        logfire.info("geocode: {waiting} rows waiting", waiting=len(rows))
        last_reported = 0
        with_coordinates: list[str] = []
        failures_in_a_row = 0
        for row in rows:
            if counts.requests >= max_requests:
                counts.stopped_at_limit = True
                break
            if not _still_ours_to_place(session, row):
                session.rollback()
                continue
            requests_before = counts.requests
            try:
                _place(session, row, geocoder, counts, max_requests, locator)
            except GeocodeBackOff as exc:
                # Nominatim said to stop, and asking again risks a ban.
                session.rollback()
                counts.skipped += 1
                _stop(counts, exc)
                break
            except GeocodeUnavailable as exc:
                # Nothing is known about the row, so it is not charged an attempt.
                session.rollback()
                counts.skipped += 1
                failures_in_a_row += 1
                if failures_in_a_row >= MAX_CONSECUTIVE_FAILURES:
                    _stop(counts, exc)
                    break
                logfire.warning("geocoder failed; skipping the row", error=str(exc))
                continue
            if counts.requests > requests_before:
                failures_in_a_row = 0
            session.commit()
            if row.lat is not None:
                with_coordinates.append(row.raw_address)
            if counts.requests - last_reported >= PROGRESS_EVERY:
                last_reported = counts.requests
                logfire.info(
                    "geocode: {requests}/{max_requests} requests, "
                    "{placed} placed, {reused} reused ({entries} entries together), "
                    "{missed} missed",
                    requests=counts.requests,
                    max_requests=max_requests,
                    placed=counts.placed,
                    reused=counts.reused,
                    entries=_entries_at(session, with_coordinates),
                    missed=counts.missed,
                )
    logfire.info(
        "geocoded: {placed} placed, {reused} reused, {missed} missed",
        placed=counts.placed,
        reused=counts.reused,
        missed=counts.missed,
    )
    return counts


def _entries_at(session: Session, raw_addresses: list[str]) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(LogEntry)
            .where(LogEntry.location.in_(raw_addresses))
        )
        or 0
    )


def _stop(counts: GeocodeCounts, exc: GeocodeUnavailable) -> None:
    counts.geocoder_unavailable = True
    counts.geocoder_error = str(exc)
    logfire.error("geocoder unavailable; stopping the run", error=str(exc))


def _rows_to_place(session: Session) -> list[AddressNormalization]:
    return list(
        session.scalars(
            select(AddressNormalization)
            .where(
                AddressNormalization.source.in_(("ai", "rule")),
                AddressNormalization.normalized_address.is_not(None),
                AddressNormalization.lat.is_(None),
                AddressNormalization.geocode_attempts < MAX_ATTEMPTS,
                # A bare highway is marked once and left for a person.
                or_(
                    AddressNormalization.kind != "highway",
                    AddressNormalization.needs_review.is_(False),
                ),
            )
            .order_by(AddressNormalization.id)
        )
    )


def _still_ours_to_place(session: Session, row: AddressNormalization) -> bool:
    """Re-read the row under a lock. A lookup can take minutes, and the admin may have
    edited the row since it was loaded. The lock holds the admin's save until we commit."""
    session.refresh(row, with_for_update=True)
    return row.source in ("ai", "rule") and row.lat is None


def _place(
    session: Session,
    row: AddressNormalization,
    geocoder: Geocoder,
    counts: GeocodeCounts,
    max_requests: int,
    locator: OsmLocator | None,
) -> None:
    if _reuse_place_code(session, row) or _reuse_same_address(session, row):
        counts.reused += 1
        return
    if _is_bare_highway(row):
        # A bare highway has no point of its own, so it gets a point on its road, as a bare
        # street does. With no road in the snapshot it is left for a person.
        match = locator.locate_highway(row) if locator is not None else None
        if match is not None:
            _apply(row, _from_match(match), counts)
            counts.placed += 1
        else:
            row.needs_review = True
            counts.bare_highways += 1
        return

    found, skipped_for_budget = _look_up(row, geocoder, counts, max_requests, locator)
    if found is None:
        if skipped_for_budget:
            # Not a real miss: the run ran out of requests before the second try.
            return
        row.geocode_attempts += 1
        if row.geocode_attempts >= MAX_ATTEMPTS:
            row.needs_review = True
        counts.missed += 1
        return
    _apply(row, found, counts)
    counts.placed += 1


def _apply(row: AddressNormalization, found: Placement, counts: GeocodeCounts) -> None:
    if found.match is not None:
        counts.from_snapshot.append(
            Placed(
                row.raw_address,
                _log_name(row),
                found.match,
                row.lat,
                row.lng,
                row.coordinate_precision,
            )
        )
    row.lat, row.lng = found.lat, found.lng
    row.coordinate_precision = found.precision
    row.geocoded_via = found.via
    row.osm_ref = found.osm_ref
    row.geocode_source_url = None


def _log_name(row: AddressNormalization) -> str:
    return (row.normalized_address or row.raw_address).split(", ")[0]


def _reuse_place_code(session: Session, row: AddressNormalization) -> bool:
    """A place code another row has already placed supplies its coordinates, when that row
    is of the same kind on the same street.

    Some dispatch codes name an area, not a place: code `E` covers a dozen streets. Two
    places with one code are the same place only on one street. A row with no street gives
    no way to tell an area from a place, so it is not given a code's pin.
    """
    if not row.place_code or not row.street:
        return False
    donor = _placed_donor(
        session,
        row,
        AddressNormalization.place_code == row.place_code,
        AddressNormalization.street == row.street,
    )
    if donor is None:
        return False
    _copy_pin(row, donor)
    row.geocoded_via = "place_code"
    return True


def _reuse_same_address(session: Session, row: AddressNormalization) -> bool:
    """Another spelling of the same normalized address has a pin, so skip the lookup."""
    donor = _placed_donor(
        session,
        row,
        AddressNormalization.normalized_address == row.normalized_address,
    )
    if donor is None:
        return False
    _copy_pin(row, donor)
    # A hand-placed pin is the best one for the address, so it is copied too.
    # `geocoded_via` says how the coordinates were found; `source` still says who owns the row.
    row.geocoded_via = donor.geocoded_via
    return True


def _placed_donor(
    session: Session, row: AddressNormalization, *same: ColumnElement[bool]
) -> AddressNormalization | None:
    if row.kind == "intersection":
        # An intersection takes only a point, so a donor on a street point lends nothing.
        same = (*same, AddressNormalization.coordinate_precision == "exact")
    return session.scalars(
        select(AddressNormalization)
        .where(
            *same,
            AddressNormalization.id != row.id,
            # A place must not inherit an address's pin, which is unrounded.
            AddressNormalization.kind == row.kind,
            AddressNormalization.lat.is_not(None),
        )
        .order_by(AddressNormalization.id)
        .limit(1)
    ).first()


def _copy_pin(row: AddressNormalization, donor: AddressNormalization) -> None:
    row.lat, row.lng = donor.lat, donor.lng
    row.coordinate_precision = donor.coordinate_precision
    row.osm_ref = donor.osm_ref
    row.geocode_source_url = donor.geocode_source_url


def _look_up(
    row: AddressNormalization,
    geocoder: Geocoder,
    counts: GeocodeCounts,
    max_requests: int,
    locator: OsmLocator | None = None,
) -> tuple[Placement | None, bool]:
    """The row's query first, then the OpenStreetMap snapshot, then its street alone, and
    whether the street was skipped for want of requests. A result outside the city is a
    miss. A query that finds only an approximate point is tried against the snapshot too,
    and keeps that point when the snapshot has nothing. An intersection takes only a
    point, so for one a street point is a miss and its street is never tried."""
    query = row.geocode_query or f"{row.normalized_address}, Lebanon, NH"
    counts.requests += 1
    found = geocoder(query)
    nominatim = found if found and in_city_bounds(found.lat, found.lng) else None
    if nominatim is not None and nominatim.precision == "exact":
        return Placement(nominatim.lat, nominatim.lng, "exact", "nominatim"), False
    if nominatim is not None and not _is_the_road_asked_for(row, nominatim):
        # A search that cannot find a road can answer with another, such as Hanover Street
        # for an exit on Interstate 89.
        nominatim = None
    if locator is not None and (match := locator.locate(row)) is not None:
        return _from_match(match), False
    if row.kind == "intersection" or _is_point_highway(row):
        # A street point is the middle of one of the two streets, not where they cross, and
        # a road point is not an exit, a mile marker or a rest area.
        return None, False
    if nominatim is not None:
        # Only a street point came back, and the snapshot has nothing better.
        return (
            Placement(nominatim.lat, nominatim.lng, nominatim.precision, "nominatim"),
            False,
        )
    if not row.street:
        return None, False
    if counts.requests >= max_requests:
        return None, True
    counts.requests += 1
    street = geocoder(f"{row.street}, Lebanon, NH")
    if (
        street is not None
        and in_city_bounds(street.lat, street.lng)
        and _is_the_road_asked_for(row, street, street_alone=True)
    ):
        # A street with no point on it is approximate, whatever the match said.
        return Placement(street.lat, street.lng, "approximate", "nominatim"), False
    return None, False


def _is_the_road_asked_for(
    row: AddressNormalization, result: GeocodeResult, *, street_alone: bool = False
) -> bool:
    """Whether an approximate answer is the street the row is on, by its name or its route
    number. The street alone is asked for by `row.street`. The row's own query also stands
    for its normalized address, which a highway row may use too."""
    highway = row.kind == "highway"
    return any(
        names_the_road(requested, name=result.name, ref=result.ref, anywhere=highway)
        for requested in _requested_streets(row, street_alone=street_alone)
    )


def _requested_streets(row: AddressNormalization, *, street_alone: bool) -> list[str]:
    streets = [row.street] if row.street else []
    normalized = row.normalized_address or ""
    if not street_alone and row.kind == "highway" and normalized:
        streets.append(normalized)
    if not streets and not street_alone and normalized:
        # No street is known, so the street part of the address, with no house number.
        part = re.sub(r"^\d+[A-Za-z]?(-\d+)?\s+", "", normalized.rpartition(", ")[2])
        streets.append(part)
    return [street for street in streets if street]


def _from_match(match: Match) -> Placement:
    return Placement(match.lat, match.lng, match.precision, "osm", match.osm_ref, match)


def _is_bare_highway(row: AddressNormalization) -> bool:
    return row.kind == "highway" and not names_a_point(row.normalized_address or "")


def _is_point_highway(row: AddressNormalization) -> bool:
    """A highway that names an exit, a mile marker, a rest area or a road it crosses takes
    only an exact point."""
    return row.kind == "highway" and names_a_point(row.normalized_address or "")


def names_a_point(normalized_address: str) -> bool:
    return _NAMES_A_POINT.search(normalized_address) is not None


def run_retry(locator: OsmLocator, *, missed: bool = False) -> GeocodeCounts:
    """Look again, from the snapshot only, at rows the job could not place well.

    By default these are the rows that sit on a street point. With `missed` they are the
    rows with no point at all that the job gave up on and marked for review. A group is the
    rows that share a normalized address and kind, joined by any place code they share. One
    lookup places the whole group, and a missed group gets its attempts reset. A group
    with a `human` row in it is left alone, and so is a group the snapshot cannot place.
    """
    counts = GeocodeCounts()
    with open_session() as session:
        groups = _missed_groups(session) if missed else _approximate_groups(session)
        for group in groups:
            counts.groups_retried += 1
            if _has_human_row(session, group):
                counts.groups_kept += 1
                continue
            rows = _still_waiting(session, group, missed=missed)
            if not rows:
                session.rollback()
                continue
            match = _first_match(locator, rows)
            if match is None:
                session.rollback()
                counts.groups_kept += 1
                continue
            for row in rows:
                _apply(row, _from_match(match), counts)
                if missed:
                    # The review mark is left alone: normalize sets it too, for an unsure
                    # answer or a street off the list, and a placed row can still need it.
                    row.geocode_attempts = 0
                counts.placed += 1
            session.commit()
    logfire.info(
        "geocode retry: {placed} rows placed in {groups} groups",
        placed=counts.placed,
        groups=counts.groups_retried,
    )
    return counts


def _first_match(locator: OsmLocator, rows: list[AddressNormalization]) -> Match | None:
    """The first row of a group the snapshot can place. Rows that would be looked up the
    same way, as spellings of one address are, are tried once."""
    tried: set[tuple[str | None, str | None, str | None]] = set()
    for row in rows:
        key = (row.normalized_address, row.kind, row.street)
        if key in tried:
            continue
        tried.add(key)
        if (match := _snapshot_match(locator, row)) is not None:
            return match
    return None


def _snapshot_match(locator: OsmLocator, row: AddressNormalization) -> Match | None:
    """What the snapshot gives for a row. A bare highway gets a point on its road, and a
    highway with an exit or a cross street is not looked up here."""
    if row.kind == "highway":
        return locator.locate_highway(row) if _is_bare_highway(row) else None
    return locator.locate(row)


def _approximate_groups(session: Session) -> list[list[AddressNormalization]]:
    return _grouped(
        list(
            session.scalars(
                select(AddressNormalization)
                .where(
                    AddressNormalization.source.in_(("ai", "rule")),
                    AddressNormalization.normalized_address.is_not(None),
                    AddressNormalization.coordinate_precision == "approximate",
                    # A highway is pinned when it is first looked up, never retried here.
                    AddressNormalization.kind.in_(("address", "place", "intersection")),
                )
                .order_by(AddressNormalization.id)
            )
        )
    )


def _missed_groups(session: Session) -> list[list[AddressNormalization]]:
    """The rows with no point that the job marked for review: three misses, or a bare
    highway with no road at the time."""
    return _grouped(
        list(
            session.scalars(
                select(AddressNormalization)
                .where(
                    AddressNormalization.source.in_(("ai", "rule")),
                    AddressNormalization.normalized_address.is_not(None),
                    AddressNormalization.lat.is_(None),
                    AddressNormalization.needs_review.is_(True),
                    AddressNormalization.kind.in_(
                        ("address", "place", "intersection", "highway")
                    ),
                )
                .order_by(AddressNormalization.id)
            )
        )
    )


def _grouped(rows: list[AddressNormalization]) -> list[list[AddressNormalization]]:
    # Rows are joined through the keys they share, so a place code links two addresses. A
    # code joins rows of one kind on one street only, like `_reuse_place_code`: a code can
    # name an area, and a row with no street is joined by its address alone.
    owner: dict[tuple[str, str], int] = {}
    groups: dict[int, list[AddressNormalization]] = {}
    for row in rows:
        keys = [("address", f"{row.normalized_address}|{row.kind}")]
        if row.place_code and row.street:
            keys.append(("code", f"{row.place_code}|{row.kind}|{row.street}"))
        joined = {owner[key] for key in keys if key in owner}
        target = min(joined) if joined else row.id
        merged = groups.setdefault(target, [])
        for other in joined - {target}:
            merged.extend(groups.pop(other))
        merged.append(row)
        for key in keys:
            owner[key] = target
        for other_key, group_id in list(owner.items()):
            if group_id in joined:
                owner[other_key] = target
    return list(groups.values())


def _has_human_row(session: Session, group: list[AddressNormalization]) -> bool:
    pairs = {(row.normalized_address, row.kind) for row in group}
    codes = {
        (row.place_code, row.kind, row.street)
        for row in group
        if row.place_code and row.street
    }
    same_address = tuple_(
        AddressNormalization.normalized_address, AddressNormalization.kind
    ).in_(pairs)
    clauses = [same_address]
    if codes:
        clauses.append(
            tuple_(
                AddressNormalization.place_code,
                AddressNormalization.kind,
                AddressNormalization.street,
            ).in_(codes)
        )
    return (
        session.scalar(
            select(AddressNormalization.id)
            .where(AddressNormalization.source == "human", or_(*clauses))
            .limit(1)
        )
        is not None
    )


def _still_waiting(
    session: Session, group: list[AddressNormalization], *, missed: bool
) -> list[AddressNormalization]:
    """Re-read each row under a lock, like `_still_ours_to_place`: the admin may have
    corrected one since the group was loaded."""
    kept = []
    for row in group:
        session.refresh(row, with_for_update=True)
        if row.source not in ("ai", "rule"):
            continue
        if missed:
            waiting = row.lat is None and row.needs_review
        else:
            waiting = row.coordinate_precision == "approximate"
        if waiting:
            kept.append(row)
    return kept


def _make_locator(
    args: argparse.Namespace,
    snapshot_dir: Path,
    backend_factory: Callable[[], AiBackend],
) -> OsmLocator | None:
    try:
        snapshot = Snapshot.load_newest(snapshot_dir)
    except FileNotFoundError as exc:
        print(f"{exc} Skipping the OpenStreetMap step.", file=sys.stderr)
        return None
    if args.no_llm:
        return OsmLocator(snapshot)
    try:
        backend = backend_factory()
        backend.check_ready()
    except AiBackendUnavailable as exc:
        print(f"No AI for place names: {exc}", file=sys.stderr)
        return OsmLocator(snapshot)
    try:
        recorder = AiCallLog(ai_calls_collection(get_db()))
    except (ValidationError, PyMongoError) as exc:
        # A plain run must not need MongoDB. Building the recorder opens no connection, so
        # the failure to expect is missing settings.
        # The type and message are logged and printed, so a real bug in the call log's setup
        # is not hidden behind "no AI".
        logfire.warning(
            "no call log; placing places without AI: {kind}: {error}",
            kind=type(exc).__name__,
            error=repr(exc),
        )
        print(
            "No AI for place names, the call log could not be set up: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return OsmLocator(snapshot)

    def picker(
        name: str, street: str, candidates: Sequence[Candidate]
    ) -> Candidate | None:
        return pick_candidate(backend, recorder, name, street, candidates)

    return OsmLocator(snapshot, picker)


def main(
    argv: Sequence[str] | None = None,
    geocoder: Geocoder = geocode,
    backend_factory: Callable[[], AiBackend] = backend_from_env,
) -> int:
    bootstrap("geocode")
    args = _parse_args(argv)
    with advisory_lock(get_engine(), GEOCODE) as acquired:
        if not acquired:
            print(
                "Another geocode run is in progress. Try again when it finishes.",
                file=sys.stderr,
            )
            return 1
        locator = _make_locator(args, DEFAULT_SNAPSHOT_DIR, backend_factory)
        retrying = args.retry_approximate or args.retry_missed
        if retrying:
            if locator is None:
                flag = "--retry-missed" if args.retry_missed else "--retry-approximate"
                print(f"{flag} needs a snapshot.", file=sys.stderr)
                return 1
            counts = run_retry(locator, missed=args.retry_missed)
        else:
            counts = run(geocoder, locator=locator)
    review_file = write_review(counts.from_snapshot, REVIEW_DIR, datetime.now())
    _print_summary(counts, locator, review_file, retry=retrying)
    if counts.stopped_at_limit:
        print(f"Stopped at {MAX_REQUESTS} requests. Run it again for the rest.")
    if counts.geocoder_unavailable:
        print(
            "Nominatim is unavailable or refused the request "
            f"({counts.geocoder_error}). Stopped early."
        )
        return 1
    return 0


@dataclass(frozen=True)
class Coverage:
    """How many parsed log entries a kind of location has, and how many sit on a pin."""

    kind: str
    entries: int
    pinned: int


NOT_NORMALIZED = "not normalized"


def coverage_by_kind(session: Session) -> list[Coverage]:
    """The share of parsed log entries with a pin, by the kind of their location. An entry
    with no location, or one the job has not normalized, counts under "not normalized"."""
    rows = session.execute(
        select(
            func.coalesce(AddressNormalization.kind, NOT_NORMALIZED),
            func.count(),
            func.count(AddressNormalization.lat),
        )
        .select_from(LogEntry)
        .outerjoin(
            AddressNormalization, AddressNormalization.raw_address == LogEntry.location
        )
        .where(LogEntry.parse_error.is_(False))
        .group_by(func.coalesce(AddressNormalization.kind, NOT_NORMALIZED))
        .order_by(func.coalesce(AddressNormalization.kind, NOT_NORMALIZED))
    ).all()
    return [Coverage(kind, entries, pinned) for kind, entries, pinned in rows]


def coverage_line(rows: Sequence[Coverage]) -> str:
    """ "Entries on a pin: 91.2% of 1,000 (address 99.0%, intersection 80.0%)". Whole tenths
    of a percent, with no float arithmetic."""
    total = sum(row.entries for row in rows)
    if total == 0:
        return "Entries on a pin: no parsed entries."
    pinned = sum(row.pinned for row in rows)
    kinds = ", ".join(f"{row.kind} {_percent(row.pinned, row.entries)}" for row in rows)
    return f"Entries on a pin: {_percent(pinned, total)} of {total:,} ({kinds})"


def _percent(part: int, whole: int) -> str:
    tenths = (part * 1000 + whole // 2) // whole
    return f"{tenths // 10}.{tenths % 10}%"


def _print_summary(
    counts: GeocodeCounts,
    locator: OsmLocator | None,
    review_file: Path | None,
    *,
    retry: bool,
) -> None:
    if retry:
        print(
            f"Retry: {counts.placed} rows placed from the snapshot, "
            f"{counts.groups_kept} of {counts.groups_retried} groups left as they were."
        )
    else:
        print(
            f"Geocoding: {counts.placed} placed, {counts.reused} reused from another row, "
            f"{counts.missed} missed, {counts.bare_highways} bare highways left for "
            f"review, {counts.skipped} skipped (will retry next run). "
            f"{counts.requests} requests."
        )
    if locator is not None:
        by_kind = ", ".join(
            f"{n} by {kind}" for kind, n in sorted(counts.found_by().items())
        )
        print(
            f"From OpenStreetMap: {len(counts.from_snapshot)} placed"
            f"{f' ({by_kind})' if by_kind else ''}. {locator.llm_calls} AI calls."
        )
        if locator.left_for_next_run:
            print(
                f"{locator.left_for_next_run} places left for the next run. "
                "Run `uv run geocode --retry-approximate` for them."
            )
    if review_file is not None:
        print(f"Review the placements in {review_file}.")
    with open_session() as session:
        print(coverage_line(coverage_by_kind(session)))


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="geocode",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    retries = parser.add_mutually_exclusive_group()
    retries.add_argument(
        "--retry-approximate",
        action="store_true",
        help="Look again, from the OpenStreetMap snapshot, at rows on a street point.",
    )
    retries.add_argument(
        "--retry-missed",
        action="store_true",
        help="Look again, from the OpenStreetMap snapshot, at rows marked for review "
        "that have no point.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Place addresses and intersections from the snapshot, but ask no AI.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
