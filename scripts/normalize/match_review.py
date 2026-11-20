"""The file a geocode run writes so Connor can skim what it placed, and undo it.

One row per placement, with the old coordinates beside the new ones, so a batch can be
reverted from the file.
"""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from locations.osm import Match, meters_between

from scripts.normalize.csv_cells import cell

DEFAULT_DIR = Path(__file__).parents[2] / "tmp"

COLUMNS = (
    "raw_address",
    "log_name",
    "matched_osm_name",
    "matched_osm_address",
    "osm_ref",
    "found_by",
    "meters_moved",
    "was_approximate",
    "old_lat",
    "old_lng",
    "old_precision",
    "new_lat",
    "new_lng",
    "new_precision",
)


@dataclass(frozen=True)
class Placed:
    raw_address: str
    log_name: str
    match: Match
    old_lat: float | None
    old_lng: float | None
    old_precision: str | None


def write_review(placed: list[Placed], directory: Path, now: datetime) -> Path | None:
    """The review file, or None when the run placed nothing."""
    if not placed:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"geocode-matches-{now:%Y%m%d-%H%M}.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for item in placed:
            writer.writerow([cell(value) for value in _row(item)])
    return path


def _row(item: Placed) -> list[object]:
    match = item.match
    moved = (
        round(meters_between(item.old_lat, item.old_lng, match.lat, match.lng))
        if item.old_lat is not None and item.old_lng is not None
        else ""
    )
    return [
        item.raw_address,
        item.log_name,
        match.name,
        match.address,
        match.osm_ref,
        match.via,
        moved,
        item.old_precision == "approximate",
        _blank(item.old_lat),
        _blank(item.old_lng),
        item.old_precision or "",
        match.lat,
        match.lng,
        "exact",
    ]


def _blank(value: float | None) -> object:
    return "" if value is None else value
