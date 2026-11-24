"""Checks on an export folder before it is uploaded.

Every check fails closed. A failure prints a count and what to look at, never the text
that matched, because the text is the thing that must not go out.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from bootstrap import bootstrap
from postgres import open_session
from postgres.models.address_normalization import AddressNormalization
from sqlalchemy import select
from sqlalchemy.orm import Session

from scripts.normalize.prompts import LOCATION_PROMPT_VERSION

DEFAULT_DIR = Path("data/export")
EXPECTED_FILES = (
    "stats.json",
    "incidents.json",
    "addresses.json",
    "activity.json",
    "staff.json",
    "properties.json",
)
# Less than this and the map is mostly empty, which means an upstream job did not finish.
COVERAGE_FLOOR = 0.85
# A shorter string, such as a street name, would match half the export.
MIN_PERSON_TEXT = 8
# Parcel and staff records are not police data, and a parcel's address may be the same
# text as a flagged location, so these two files are not scanned.
NOT_POLICE_DATA = ("properties.json", "staff.json")


def check_files(export: Path) -> list[str]:
    """Every expected file is there, and every pin on the map has its place card."""
    problems = [
        f"{name} is missing" for name in EXPECTED_FILES if not (export / name).is_file()
    ]
    if problems:
        return problems
    addresses = json.loads((export / "addresses.json").read_text())
    missing = [
        a["id"]
        for a in addresses
        if not (export / "places" / f"{a['id']}.json").is_file()
    ]
    if missing:
        problems.append(f"{len(missing)} places have no card file")
    return problems


def check_coverage(export: Path) -> list[str]:
    """The share of in-range entries that sit on a pin is at or above the floor."""
    stats = json.loads((export / "stats.json").read_text())
    total, mapped = stats["total"], stats["mapped_total"]
    if total <= 0:
        return ["stats.json counts no entries"]
    if mapped / total < COVERAGE_FLOOR:
        return [f"coverage is {mapped / total:.1%}, below {COVERAGE_FLOOR:.0%}"]
    return []


def check_person_text(export: Path, session: Session) -> list[str]:
    """No location flagged as naming a person appears anywhere in the export."""
    rows = session.execute(
        select(
            AddressNormalization.raw_address,
            AddressNormalization.normalized_address,
            AddressNormalization.street,
        ).where(AddressNormalization.names_person.is_(True))
    ).all()
    # Two raw values can normalize to one address, so a flagged row may share its
    # normalized text with an unflagged row. That text is public through the other row.
    public_texts = {
        text.casefold()
        for raw, normalized in session.execute(
            select(
                AddressNormalization.raw_address,
                AddressNormalization.normalized_address,
            ).where(AddressNormalization.names_person.is_(False))
        ).all()
        for text in (raw, normalized)
        if text
    }
    texts = {
        text.casefold()
        for raw, normalized, street in rows
        for text in (raw, normalized)
        if text and len(text) >= MIN_PERSON_TEXT and text != street
    } - public_texts
    exported = "\n".join(
        path.read_text()
        for path in export.rglob("*.json")
        if path.name not in NOT_POLICE_DATA
    ).casefold()
    found = sum(1 for text in texts if text in exported)
    return [f"{found} flagged person locations appear in the export"] if found else []


def check_prompt_versions(session: Session) -> list[str]:
    """No location in the export was answered by an old prompt.

    Rule rows store their own version, so only AI rows are counted.
    """
    stale = session.scalars(
        select(AddressNormalization.id).where(
            AddressNormalization.source == "ai",
            AddressNormalization.normalized_address.is_not(None),
            AddressNormalization.prompt_version.not_like(f"{LOCATION_PROMPT_VERSION}%"),
        )
    ).all()
    return [f"{len(stale)} AI locations are on an old prompt"] if stale else []


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check-export", description=__doc__)
    parser.add_argument("export", nargs="?", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)
    bootstrap("check_export")

    problems = check_files(args.export)
    if not problems:
        problems += check_coverage(args.export)
        with open_session() as session:
            problems += check_prompt_versions(session)
            problems += check_person_text(args.export, session)
    for problem in problems:
        print(f"check-export: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"✓ {args.export} passed every check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
