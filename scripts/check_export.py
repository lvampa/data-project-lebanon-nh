"""Checks on an export folder before it is uploaded.

Every check fails closed. A failure prints a count and what to look at, never the text
that matched, because the text is the thing that must not go out.
"""

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path

from bootstrap import bootstrap
from postgres import open_session
from postgres.models.address_normalization import AddressNormalization
from sqlalchemy import select
from sqlalchemy.orm import Session

from scripts.normalize.prompts import MIN_PRIVACY_LOCATION_PROMPT

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
    """No flagged location's text appears in the export.

    A flagged row's raw text is never published, so it must not appear at all. Its
    normalized text may appear only when an unflagged location has the same text, since two
    raw values can normalize to one address and the unflagged row publishes it. A held row
    is checked like any other: a hold keeps it out of the view, so its text appearing means
    something else published it.
    """
    rows = session.execute(
        select(
            AddressNormalization.raw_address,
            AddressNormalization.normalized_address,
            AddressNormalization.street,
        ).where(AddressNormalization.names_person.is_(True))
    ).all()
    unflagged_texts = {
        normalized.casefold()
        for normalized in session.scalars(
            select(AddressNormalization.normalized_address).where(
                AddressNormalization.names_person.is_(False),
                AddressNormalization.normalized_address.is_not(None),
            )
        )
        if normalized
    }

    def scannable(text: str | None, street: str | None) -> str | None:
        if text and len(text) >= MIN_PERSON_TEXT and text != street:
            return text.casefold()
        return None

    raw_texts = {scannable(raw, street) for raw, _, street in rows}
    normalized_texts = {
        scannable(normalized, street) for _, normalized, street in rows
    } - unflagged_texts
    texts = (raw_texts | normalized_texts) - {None}
    exported = "\n".join(
        path.read_text()
        for path in export.rglob("*.json")
        if path.name not in NOT_POLICE_DATA
    ).casefold()
    found = sum(1 for text in texts if text and text in exported)
    return [f"{found} flagged person locations appear in the export"] if found else []


def location_prompt_number(prompt_version: str | None) -> int | None:
    """The number in `location-3+streets-<hash>`. The suffix changes with the street list."""
    match = re.match(r"location-(\d+)", prompt_version or "")
    return int(match.group(1)) if match else None


def check_prompt_versions(session: Session) -> list[str]:
    """No AI location in the export predates the prompt that flags a person.

    Rule rows store their own version, so only AI rows are counted.
    """
    versions = session.scalars(
        select(AddressNormalization.prompt_version).where(
            AddressNormalization.source == "ai",
            AddressNormalization.normalized_address.is_not(None),
        )
    ).all()
    numbers = [location_prompt_number(version) for version in versions]
    stale = sum(1 for n in numbers if n is None or n < MIN_PRIVACY_LOCATION_PROMPT)
    return (
        [f"{stale} AI locations are on a prompt without the person flag"]
        if stale
        else []
    )


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
