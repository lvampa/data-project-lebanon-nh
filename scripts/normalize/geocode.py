"""Put normalized locations on the map, by hand from Connor's Mac.

    uv run geocode

It takes `ai` and `rule` rows that have a normalized address and no coordinates, and
never a `human` row. It reuses the coordinates of a place code another row already
has, or the coordinates of another spelling of the same address. Otherwise it asks the
geocoder for the row's query and then for its street alone, and drops a result outside
the city. A row that misses three times is marked for review. It stops
after 600 requests, and leaves the rest for the next run.

A row whose lookup times out, cannot connect or gets a 5xx is skipped and not charged
an attempt, so the next run tries it again. A 403 or 429 stops the run at once, and so
do 5 skipped rows in a row. The exit code stays 0 when rows were only skipped, and the
summary says how many.
"""

import argparse
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import logfire
from bootstrap import bootstrap
from locations.geocode import (
    GeocodeBackOff,
    GeocodeResult,
    GeocodeUnavailable,
    geocode,
    in_city_bounds,
)
from postgres import get_engine, open_session
from postgres.lock import police_log_lock
from postgres.models.address_normalization import AddressNormalization
from postgres.models.log_entry import LogEntry
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

MAX_ATTEMPTS = 3
MAX_REQUESTS = 600
# Rows in a row that fail with a timeout, a connection error or a 5xx before the run
# assumes the service, or our network, is down.
MAX_CONSECUTIVE_FAILURES = 5
PROGRESS_EVERY = 50

Geocoder = Callable[[str], GeocodeResult | None]

# A highway names a point when it gives a cross street, an exit, or a landmark. The
# last is a guess: anything that says "near" or "at".
_NAMES_A_POINT = re.compile(r"\b(and|exit|near|at)\b|&", re.IGNORECASE)


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


def run(
    geocoder: Geocoder = geocode, *, max_requests: int = MAX_REQUESTS
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
                _place(session, row, geocoder, counts, max_requests)
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
) -> None:
    if _reuse_place_code(session, row) or _reuse_same_address(session, row):
        counts.reused += 1
        return
    if row.kind == "highway" and not _names_a_point(row.normalized_address or ""):
        row.needs_review = True
        counts.bare_highways += 1
        return

    found, skipped_for_budget = _look_up(row, geocoder, counts, max_requests)
    if found is None:
        if skipped_for_budget:
            # Not a real miss: the run ran out of requests before the second try.
            return
        row.geocode_attempts += 1
        if row.geocode_attempts >= MAX_ATTEMPTS:
            row.needs_review = True
        counts.missed += 1
        return
    row.lat, row.lng = found.lat, found.lng
    row.coordinate_precision = found.precision
    row.geocoded_via = "nominatim"
    counts.placed += 1


def _reuse_place_code(session: Session, row: AddressNormalization) -> bool:
    """A place code another row has already placed supplies its coordinates."""
    if not row.place_code:
        return False
    donor = _placed_donor(
        session, row, AddressNormalization.place_code == row.place_code
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


def _look_up(
    row: AddressNormalization,
    geocoder: Geocoder,
    counts: GeocodeCounts,
    max_requests: int,
) -> tuple[GeocodeResult | None, bool]:
    """The row's query first, then its street alone, and whether the street was skipped
    for want of requests. A result outside the city is a miss."""
    query = row.geocode_query or f"{row.normalized_address}, Lebanon, NH"
    counts.requests += 1
    found = geocoder(query)
    if found is not None and in_city_bounds(found.lat, found.lng):
        return found, False
    if not row.street:
        return None, False
    if counts.requests >= max_requests:
        return None, True
    counts.requests += 1
    street = geocoder(f"{row.street}, Lebanon, NH")
    if street is not None and in_city_bounds(street.lat, street.lng):
        # A street with no point on it is approximate, whatever the match said.
        return GeocodeResult(street.lat, street.lng, "approximate"), False
    return None, False


def _names_a_point(normalized_address: str) -> bool:
    return _NAMES_A_POINT.search(normalized_address) is not None


def main(argv: Sequence[str] | None = None, geocoder: Geocoder = geocode) -> int:
    bootstrap("geocode")
    # It takes no options, but parsing still makes --help print usage instead of
    # running the job.
    argparse.ArgumentParser(
        prog="geocode",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    ).parse_args(argv)
    with police_log_lock(get_engine()) as acquired:
        if not acquired:
            print(
                "Another police log job is running (process, reprocess, or "
                "normalize). Try again when it finishes.",
                file=sys.stderr,
            )
            return 1
        counts = run(geocoder)
    print(
        f"Geocoding: {counts.placed} placed, {counts.reused} reused from another row, "
        f"{counts.missed} missed, {counts.bare_highways} bare highways left for review, "
        f"{counts.skipped} skipped (will retry next run). "
        f"{counts.requests} requests."
    )
    if counts.stopped_at_limit:
        print(f"Stopped at {MAX_REQUESTS} requests. Run it again for the rest.")
    if counts.geocoder_unavailable:
        print(
            "Nominatim is unavailable or refused the request "
            f"({counts.geocoder_error}). Stopped early."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
