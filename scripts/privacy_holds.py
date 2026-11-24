"""Hold locations that name a person out of the public data until someone has handled them.

`mark` holds every flagged location that is not clearly safe. The public views then treat
a held location as unmapped: its entries stay in the log and the counts, with no location
and no pin. `list` shows what is held, and `handled` releases a location, which then
publishes as any flagged location does, as its street only. `mark` never clears a hold.

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


def is_plain_address(text: str, streets: Collection[str]) -> bool:
    """A street, or a house number and a street, from the street list. Lowercase."""
    match = re.match(r"\d+[a-z]?(-\d+)? (.+)$", text)
    return text in streets or bool(match and match.group(2) in streets)


def is_clearly_safe(
    normalized: str | None, streets: Collection[str], unflagged_texts: Collection[str]
) -> bool:
    """Whether a flagged location can be published as the view would publish it.

    The view never publishes a flagged row's raw text, and publishes only its street. So the
    text that could name someone is its normalized address, and that is safe when it is a
    plain address or street, or when an unflagged location has the same normalized text and
    publishes it already. A location with no normalized address is not clearly safe.
    """
    if normalized is None:
        return False
    text = normalized.casefold()
    return is_plain_address(text, streets) or text in unflagged_texts


def mark(session: Session) -> tuple[int, int]:
    """Hold every flagged location that is not clearly safe. Returns (newly held, safe)."""
    streets = {
        street.casefold()
        for street in session.scalars(
            select(AddressNormalization.street).where(
                AddressNormalization.street.is_not(None)
            )
        )
        if street
    }
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
    flagged = session.execute(
        select(AddressNormalization).where(AddressNormalization.names_person.is_(True))
    ).scalars()
    held = safe = 0
    for row in flagged:
        if is_clearly_safe(row.normalized_address, streets, unflagged_texts):
            safe += 1
        elif not row.privacy_hold:
            row.privacy_hold = True
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
