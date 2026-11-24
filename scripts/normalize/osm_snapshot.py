"""Save a snapshot of Lebanon, NH from OpenStreetMap, for the geocode job.

    uv run osm-snapshot [--dir scripts/data/osm]

It makes three Overpass requests, one for every named or numbered feature in the city,
one for every named road, and one for every highway exit, and writes them to `snapshot-YYYY-MM-DD.json`. The
geocode job reads the newest snapshot and makes no Overpass request of its own. Run
this again when the map changes, which is rarely.
"""

import argparse
import sys
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import logfire
from bootstrap import bootstrap
from locations.osm import Snapshot, snapshot_from_replies
from locations.overpass import (
    FEATURES_QUERY,
    JUNCTIONS_QUERY,
    ROADS_QUERY,
    OverpassUnavailable,
    overpass_query,
)

DEFAULT_DIR = Path(__file__).parents[1] / "data" / "osm"

Query = Callable[[str], dict[str, Any]]


def build_snapshot(today: date, query: Query = overpass_query) -> Snapshot:
    snapshot = snapshot_from_replies(
        today.isoformat(),
        query(FEATURES_QUERY),
        query(ROADS_QUERY),
        query(JUNCTIONS_QUERY),
    )
    if not snapshot.features or not snapshot.roads:
        # An area that matched nothing returns no elements, and an empty snapshot would
        # look like a good one.
        raise OverpassUnavailable(
            "Overpass returned no features or roads for Lebanon. "
            "Check the boundary tags in locations/overpass.py."
        )
    return snapshot


def write_snapshot(snapshot: Snapshot, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"snapshot-{snapshot.fetched_at}.json"
    path.write_text(snapshot.to_json())
    return path


def main(argv: Sequence[str] | None = None, query: Query = overpass_query) -> int:
    bootstrap("osm_snapshot")
    parser = argparse.ArgumentParser(
        prog="osm-snapshot",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)
    try:
        snapshot = build_snapshot(date.today(), query)
    except OverpassUnavailable as exc:
        print(f"Snapshot failed: {exc}", file=sys.stderr)
        return 1
    path = write_snapshot(snapshot, args.dir)
    logfire.info("osm snapshot written", path=str(path))
    print(
        f"Wrote {path}: {len(snapshot.features)} features, {len(snapshot.roads)} roads, "
        f"{len(snapshot.junctions)} exits."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
