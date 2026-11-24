"""Hold locations that name a person out of the public data until someone has handled them.

`mark` holds every flagged location that is not clearly safe, and every other location with
the same normalized text, flagged or not. The public views then treat a held location as
unmapped: its entries stay in the log and the counts, with no location and no pin. `list`
shows what is held, and `handled` releases a location, which then publishes as any flagged
location does, as its street only. `mark` never clears a hold, but it holds a handled
location again when its normalized text is no longer the one that was handled.

Only `list` prints a location's text, to the terminal of the person running it. Everything
else prints counts.
"""

import argparse
import re
import sys
from collections.abc import Collection, Sequence
from datetime import UTC, datetime

from bootstrap import bootstrap
from postgres import open_session
from postgres.models.address_normalization import AddressNormalization
from sqlalchemy import select
from sqlalchemy.orm import Session

from scripts.normalize.streets import load_street_list


def street_set(session: Session) -> set[str]:
    """The street list the AI was given, in lowercase."""
    return {street.casefold() for street in load_street_list(session)}


def is_plain_address(text: str, streets: Collection[str]) -> bool:
    """A street, or a house number and a street, from the street list. Lowercase."""
    match = re.match(r"\d+[a-z]?(-\d+)? (.+)$", text)
    return text in streets or bool(match and match.group(2) in streets)


def is_clearly_safe(normalized: str | None, streets: Collection[str]) -> bool:
    """Whether a flagged location can be published as the view would publish it.

    The view never publishes a flagged row's raw text, and publishes only its street. So the
    text that could name someone is its normalized address, and that is safe only when it is
    a plain address or street from the street list. A location with no normalized address is
    not clearly safe. Another row with the same text does not make it safe, since that row
    could carry the name too.
    """
    return normalized is not None and is_plain_address(normalized.casefold(), streets)


def _folded(text: str | None) -> str:
    return (text or "").casefold()


def mark(session: Session) -> tuple[int, int]:
    """Hold what is not clearly safe. Returns (newly held, flagged rows clearly safe)."""
    streets = street_set(session)
    rows = list(session.scalars(select(AddressNormalization)))
    unsafe_texts: set[str] = set()
    to_hold: list[AddressNormalization] = []
    safe = 0
    for row in rows:
        if not row.names_person:
            continue
        if is_clearly_safe(row.normalized_address, streets):
            safe += 1
        elif row.normalized_address is None:
            to_hold.append(row)
        else:
            unsafe_texts.add(_folded(row.normalized_address))
    to_hold += [
        row
        for row in rows
        if row.normalized_address is not None
        and _folded(row.normalized_address) in unsafe_texts
    ]
    held = 0
    for row in to_hold:
        if not row.privacy_hold:
            row.privacy_hold = True
            held += 1
        elif row.privacy_handled_at is not None and row.privacy_handled_text != _folded(
            row.normalized_address
        ):
            row.privacy_handled_at = None
            held += 1
    session.commit()
    return held, safe


def waiting(session: Session) -> list[AddressNormalization]:
    return list(
        session.scalars(
            select(AddressNormalization)
            .where(
                AddressNormalization.privacy_hold.is_(True),
                AddressNormalization.privacy_handled_at.is_(None),
            )
            .order_by(AddressNormalization.id)
        )
    )


def handle(session: Session, ids: Sequence[int]) -> int:
    """Release the held locations with these ids. Returns how many were released."""
    released = 0
    now = datetime.now(UTC)
    for row in session.scalars(
        select(AddressNormalization).where(AddressNormalization.id.in_(ids))
    ):
        if row.privacy_hold and row.privacy_handled_at is None:
            row.privacy_handled_at = now
            row.privacy_handled_text = _folded(row.normalized_address)
            released += 1
    session.commit()
    return released


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="privacy-holds", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("mark", help="hold flagged locations that are not clearly safe")
    commands.add_parser("list", help="print the held locations, for the operator only")
    handled = commands.add_parser("handled", help="release held locations by id")
    handled.add_argument("ids", nargs="+", type=int)
    args = parser.parse_args(argv)
    bootstrap("privacy_holds")

    with open_session() as session:
        if args.command == "mark":
            held, safe = mark(session)
            print(f"privacy-holds: {held} newly held, {safe} clearly safe")
        elif args.command == "list":
            rows = waiting(session)
            for row in rows:
                print(f"{row.id}\t{row.kind}\t{row.raw_address}")
            print(f"privacy-holds: {len(rows)} held", file=sys.stderr)
        else:
            released = handle(session, args.ids)
            print(f"privacy-holds: {released} released")
    return 0


if __name__ == "__main__":
    sys.exit(main())
