"""Operator commands for the police log pipeline.

Run from scrapers/:

    uv run python -m maintenance.police_logs errors
    uv run python -m maintenance.police_logs reset URL [URL ...]
    uv run python -m maintenance.police_logs unmatched-dispositions

`errors` lists the URL records the process job gave up on, with the reason.
`reset` sends chosen ones back to pending, so the next process run tries them again.
`unmatched-dispositions` lists entries whose reason and action text ended in no known
disposition. Add the new ending to parsers/dispositions.py, bump PARSER_VERSION, and
reprocess.
"""

import argparse
import sys
from collections.abc import Sequence

from postgres import SessionLocal
from postgres.models.log_entry import LogEntry
from postgres.models.pdf_url import PdfUrl
from sqlalchemy import select, update


def list_errors() -> int:
    with SessionLocal() as session:
        rows = session.scalars(
            select(PdfUrl)
            .where(PdfUrl.state == "error")
            .order_by(PdfUrl.log_date, PdfUrl.id)
        ).all()
    if not rows:
        print("No URL records in error.")
        return 0
    for row in rows:
        print(
            f"{row.log_date}  {row.error_kind or '-':<8} attempts {row.attempts}  "
            f"{row.canonical_url}\n    {row.error_message}"
        )
    return 0


def reset(urls: Sequence[str]) -> int:
    """Send URL records in error back to pending. Report any that cannot be reset."""
    problems = []
    reset_count = 0
    with SessionLocal() as session:
        for canonical_url in urls:
            state = session.scalar(
                select(PdfUrl.state).where(PdfUrl.canonical_url == canonical_url)
            )
            if state is None:
                problems.append(f"{canonical_url}: no such URL record")
            elif state != "error":
                problems.append(f"{canonical_url}: not in error (it is {state})")
            else:
                session.execute(
                    update(PdfUrl)
                    .where(PdfUrl.canonical_url == canonical_url)
                    # The attempt count restarts, or a URL that used up its 3
                    # attempts would be given up on after its next failure.
                    .values(
                        state="pending",
                        attempts=0,
                        error_kind=None,
                        error_message=None,
                    )
                )
                reset_count += 1
        session.commit()
    print(f"Reset {reset_count} URL records to pending.")
    if problems:
        print("\n".join(problems), file=sys.stderr)
    return 1 if problems else 0


def list_unmatched_dispositions() -> int:
    with SessionLocal() as session:
        rows = session.execute(
            select(LogEntry.case_number, LogEntry.log_date, LogEntry.incident_type)
            .where(LogEntry.disposition_unmatched)
            .order_by(LogEntry.log_date.desc(), LogEntry.case_number)
        ).all()
    if not rows:
        print("No entries with an unmatched disposition.")
        return 0
    for case_number, log_date, text in rows:
        print(f"{case_number}  {log_date}  {text}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="police_logs")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("errors", help="List URL records in error, with reasons.")
    reset_parser = commands.add_parser(
        "reset", help="Send URL records in error back to pending."
    )
    reset_parser.add_argument("urls", nargs="+", metavar="URL")
    commands.add_parser(
        "unmatched-dispositions",
        help="List entries whose text ended in no known disposition.",
    )

    args = parser.parse_args(argv)
    if args.command == "errors":
        return list_errors()
    if args.command == "reset":
        return reset(args.urls)
    return list_unmatched_dispositions()


if __name__ == "__main__":
    sys.exit(main())
