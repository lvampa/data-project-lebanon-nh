"""Put places on the map by hand, in bulk, from a spreadsheet.

    uv run place-sheet export [PATH] [--since 2026-01-01]
    uv run place-sheet import PATH

`export` writes the places that still sit on their street's point, busiest first: a
CSV with the address, street, current coordinates, calls, and a link to OpenStreetMap,
and two empty columns, `lat` and `lng`. Fill them in for the places you can find, and
leave the rest blank.

`import` reads the file back. A row with both columns filled sets every row for that
address to those coordinates as a `human` placement, which the geocode job never
changes. If the row also has a `source_url` (an http or https link to the page that
gave the spot), the pin is a `research` pin instead: exact, with the link kept, but the
row stays `ai` or `rule`, since a person did not check it. A blank row is skipped, and a row with a bad number, or a point outside
Lebanon, is rejected with its line number and changes nothing.
"""

import argparse
import csv
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from bootstrap import bootstrap
from locations.geocode import in_city_bounds
from postgres import get_engine, open_session, utc_now
from postgres.lock import GEOCODE, advisory_lock
from postgres.models.address_normalization import AddressNormalization
from sqlalchemy import CursorResult, func, text, update
from sqlalchemy.orm import Session

from scripts.normalize.csv_cells import cell, uncell
from scripts.normalize.match_review import DEFAULT_DIR

DEFAULT_SINCE = date(2026, 1, 1)
COLUMNS = (
    "normalized_address",
    "name",
    "street",
    "current_lat",
    "current_lng",
    "calls",
    "openstreetmap",
    "lat",
    "lng",
    "source_url",
)
# What a person's own placement sets besides the pin. A researched pin leaves all of it, since
# nobody checked it.
_HUMAN_PLACEMENT = {
    "source": "human",
    "needs_review": False,
    "prompt_version": None,
}
# The same tolerance on a coordinate that was written to the sheet and read back.
_SAME_POINT = 1e-7

# Places and house addresses on a street point, with the calls the map counts for them:
# every call except road traffic. A bare street is a road, so it is not listed. The
# category lives in the call_category() function, so the list exists once.
_APPROXIMATE_PLACES = text(
    """
    SELECT an.normalized_address, an.lat, an.lng, MODE() WITHIN GROUP (ORDER BY an.street) AS street,
           COUNT(*) FILTER (
               WHERE call_category(le.incident_type, le.call_source) <> 'traffic'
           ) AS calls
    FROM address_normalizations an
    JOIN log_entries le ON le.location = an.raw_address
    WHERE an.source IN ('ai', 'rule')
      AND an.coordinate_precision = 'approximate'
      AND an.kind IN ('place', 'address')
      AND an.normalized_address IS NOT NULL
      AND (strpos(an.normalized_address, ', ') > 0 OR an.normalized_address ~ '^\\d')
      AND le.parse_error = false
      AND le.log_date >= :since
    GROUP BY an.normalized_address, an.lat, an.lng
    HAVING COUNT(*) FILTER (
               WHERE call_category(le.incident_type, le.call_source) <> 'traffic'
           ) > 0
    ORDER BY calls DESC, an.normalized_address
    """
)


@dataclass
class ImportResult:
    changed_places: int = 0
    changed_rows: int = 0
    blank: int = 0
    # (line number in the file, why)
    rejected: list[tuple[int, str]] = field(default_factory=list)


def export_sheet(session: Session, path: Path, since: date = DEFAULT_SINCE) -> int:
    """Write the sheet, and return how many places it lists."""
    rows = session.execute(_APPROXIMATE_PLACES, {"since": since}).all()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow(
                [
                    cell(row.normalized_address),
                    cell(row.normalized_address.split(", ")[0]),
                    cell(row.street or ""),
                    row.lat,
                    row.lng,
                    row.calls,
                    _map_link(row.lat, row.lng),
                    "",
                    "",
                    "",
                ]
            )
    return len(rows)


def _map_link(lat: float, lng: float) -> str:
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lng}#map=18/{lat}/{lng}"


def import_sheet(session: Session, path: Path) -> ImportResult:
    result = ImportResult()
    with path.open(newline="") as handle:
        for line, row in enumerate(csv.DictReader(handle), start=2):
            _import_row(session, line, row, result)
    session.commit()
    return result


def _import_row(
    session: Session, line: int, row: dict[str, str], result: ImportResult
) -> None:
    typed_lat = (row.get("lat") or "").strip()
    typed_lng = (row.get("lng") or "").strip()
    if not typed_lat and not typed_lng:
        result.blank += 1
        return
    try:
        lat, lng = float(typed_lat), float(typed_lng)
        current = (float(row["current_lat"]), float(row["current_lng"]))
    except (ValueError, KeyError):
        result.rejected.append((line, "lat and lng must both be numbers"))
        return
    if not in_city_bounds(lat, lng):
        result.rejected.append((line, f"{lat}, {lng} is outside Lebanon"))
        return
    source_url = uncell((row.get("source_url") or "").strip())
    if source_url and not _is_web_url(source_url):
        result.rejected.append((line, "source_url must be an http or https link"))
        return
    changed = _place_by_hand(
        session,
        uncell(row.get("normalized_address", "")),
        current,
        lat,
        lng,
        source_url or None,
    )
    if changed == 0:
        result.rejected.append(
            (line, "no row is still on that street point, so nothing was changed")
        )
        return
    result.changed_places += 1
    result.changed_rows += changed


def _place_by_hand(
    session: Session,
    normalized_address: str,
    current: tuple[float, float],
    lat: float,
    lng: float,
    source_url: str | None,
) -> int:
    """Set every ai or rule row for the address that still sits on the sheet's point. A
    human row is never matched, and a row the geocode job moved since is left as it is.

    With a source URL the pin is `research`: found on a page, not checked by a person, so
    `source` stays as it is. Without one it is the person's own placement."""
    researched = source_url is not None
    changed = cast(
        "CursorResult[Any]",
        session.execute(
            update(AddressNormalization)
            .where(
                AddressNormalization.normalized_address == normalized_address,
                AddressNormalization.source.in_(("ai", "rule")),
                AddressNormalization.coordinate_precision == "approximate",
                func.abs(AddressNormalization.lat - current[0]) < _SAME_POINT,
                func.abs(AddressNormalization.lng - current[1]) < _SAME_POINT,
            )
            .values(
                lat=lat,
                lng=lng,
                geocoded_via="research" if researched else "manual",
                # A point typed by hand is a point, whatever the last lookup said.
                coordinate_precision="exact",
                osm_ref=None,
                geocode_source_url=source_url,
                updated_at=utc_now(),
                **({} if researched else _HUMAN_PLACEMENT),
            )
        ),
    )
    return changed.rowcount


def _is_web_url(value: str) -> bool:
    parts = urlparse(value)
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def main(argv: Sequence[str] | None = None) -> int:
    bootstrap("place_sheet")
    args = _parse_args(argv)
    with advisory_lock(get_engine(), GEOCODE) as acquired:
        # The geocode lock, so a run of the job cannot move a row mid-import.
        if not acquired:
            print(
                "A geocode run is in progress. Try again when it finishes.",
                file=sys.stderr,
            )
            return 1
        with open_session() as session:
            if args.command == "export":
                path = (
                    args.path or DEFAULT_DIR / f"place-sheet-{date.today():%Y%m%d}.csv"
                )
                count = export_sheet(session, path, args.since)
                print(
                    f"Wrote {count} places to {path}. Fill in lat and lng, then import it."
                )
                return 0
            result = import_sheet(session, args.path)
    print(
        f"{result.changed_places} places set by hand ({result.changed_rows} rows), "
        f"{result.blank} blank rows skipped, {len(result.rejected)} rejected."
    )
    for line, why in result.rejected:
        print(f"  line {line}: {why}")
    return 1 if result.rejected else 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="place-sheet",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="Write the sheet.")
    export.add_argument("path", type=Path, nargs="?")
    export.add_argument("--since", type=date.fromisoformat, default=DEFAULT_SINCE)
    read = commands.add_parser("import", help="Read the filled sheet back.")
    read.add_argument("path", type=Path)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
