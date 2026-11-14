"""Normalize incident types and locations with AI, by hand from Connor's Mac.

Run from the repo root, with Postgres and MongoDB up (`docker compose up -d postgres
mongo`) and `claude` logged in:

    uv run normalize [--field incident_type|location] [--redo]

The job is a workflow, not an agent. Code finds the waiting values, settles what rules
can, sends the rest in batches to a backend that has no tools, checks every answer,
and stores what passes. The backend never sees a database.
"""

import argparse
import json
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import logfire
from mongo.ai_calls import AiCall, AiCallLog, Outcome, ai_calls_collection
from mongo.client import MongoDB
from postgres import SessionLocal, engine
from postgres.lock import police_log_lock

from scripts.normalize.backends import (
    AiBackend,
    AiBackendUnavailable,
    AiCallFailed,
    backend_from_env,
)
from scripts.normalize.checks import AnswerOffSchema
from scripts.normalize.fields import Field, Group, IncidentTypes, Locations
from scripts.normalize.streets import load_street_list

BATCH_SIZE = 50
CALLS_PER_FIELD = 5
FIELD_NAMES = ("incident_type", "location")


@dataclass(frozen=True)
class FieldSummary:
    field: str
    # Rows written this run: settled by a copy or a rule, or stored from an AI answer.
    normalized: int = 0
    # Values whose item was discarded or missing, each charged a failed attempt.
    discarded: int = 0
    # Values still waiting for a normalization after the run.
    waiting: int = 0


@dataclass
class RunResult:
    summaries: list[FieldSummary] = field(default_factory=list)
    calls: int = 0
    failed_calls: int = 0
    records_lost: int = 0
    stopped: bool = False
    street_list_was_empty: bool = False

    def summary(self, name: str) -> FieldSummary:
        return next(s for s in self.summaries if s.field == name)

    @property
    def every_call_failed(self) -> bool:
        return self.calls > 0 and self.failed_calls == self.calls


def allocate_calls(
    needed: Mapping[str, int], per_field: int = CALLS_PER_FIELD
) -> dict[str, int]:
    """Each field may make `per_field` calls, and calls it does not use pass to the
    others (9.6)."""
    allowed = {name: min(count, per_field) for name, count in needed.items()}
    spare = sum(per_field - count for count in allowed.values())
    for name, count in needed.items():
        extra = min(count - allowed[name], spare)
        allowed[name] += extra
        spare -= extra
    return allowed


def run(
    backend: AiBackend,
    call_log: AiCallLog,
    *,
    fields: Sequence[str],
    redo: bool,
    batch_size: int = BATCH_SIZE,
) -> RunResult:
    result = RunResult()
    with SessionLocal() as session:
        streets = load_street_list(session)
        every_field: dict[str, Field] = {
            "incident_type": IncidentTypes(),
            "location": Locations(streets),
        }
        chosen = [every_field[name] for name in FIELD_NAMES if name in fields]
        result.street_list_was_empty = "location" in fields and not streets
        if result.street_list_was_empty:
            logfire.error(
                "no streets in the parcel table; no location AI calls this run. "
                "Run the VGSI scrape first."
            )

        settled: dict[str, int] = {}
        batches: dict[str, list[list[Group]]] = {name: [] for name in FIELD_NAMES}
        for chosen_field in chosen:
            plan = chosen_field.plan(session, redo)
            session.commit()
            settled[chosen_field.name] = plan.settled
            if chosen_field.can_call():
                batches[chosen_field.name] = _chunks(plan.groups, batch_size)

        allowed = allocate_calls({n: len(b) for n, b in batches.items()})
        discarded = {f.name: 0 for f in chosen}
        written = dict(settled)
        for chosen_field in chosen:
            for batch in batches[chosen_field.name][: allowed[chosen_field.name]]:
                if result.stopped:
                    break
                outcome = _call(session, backend, call_log, chosen_field, batch, result)
                written[chosen_field.name] += outcome.stored
                discarded[chosen_field.name] += outcome.discarded

        for chosen_field in chosen:
            result.summaries.append(
                FieldSummary(
                    chosen_field.name,
                    written[chosen_field.name],
                    discarded[chosen_field.name],
                    chosen_field.waiting(session),
                )
            )
    for summary in result.summaries:
        logfire.info(
            "normalized {field}: {normalized} stored, {discarded} discarded, "
            "{waiting} waiting",
            field=summary.field,
            normalized=summary.normalized,
            discarded=summary.discarded,
            waiting=summary.waiting,
        )
    return result


@dataclass(frozen=True)
class _BatchOutcome:
    stored: int = 0
    discarded: int = 0


def _call(
    session: Any,
    backend: AiBackend,
    call_log: AiCallLog,
    chosen: Field,
    batch: list[Group],
    result: RunResult,
) -> _BatchOutcome:
    request = chosen.request(batch)
    by_sent = {group.sent: group for group in batch}
    started = time.monotonic()
    called_at = datetime.now(UTC)
    result.calls += 1

    answer: dict[str, Any] | None = None
    checked = None
    outcome: Outcome = "failed"
    error: str | None = None
    try:
        answer = backend.complete(request.prompt, request.schema)
        checked = chosen.check(answer, request.sent)
        outcome = (
            "ok"
            if not (checked.discarded or checked.missing or checked.not_sent)
            else "partial"
        )
    except AiBackendUnavailable as exc:
        outcome, error, result.stopped = "unavailable", str(exc), True
        logfire.error("ai backend unavailable; no more calls this run", error=error)
    except (AiCallFailed, AnswerOffSchema) as exc:
        error = str(exc)
        logfire.warning("ai call failed", field=chosen.name, error=error)
    if outcome in ("failed", "unavailable"):
        result.failed_calls += 1

    accepted_items = (
        [entry.item.model_dump() for entry in checked.accepted] if checked else []
    )
    call_id = call_log.record(
        AiCall(
            field=chosen.name,
            raw_values=request.sent,
            prompt=request.prompt,
            raw_answer=json.dumps(answer) if answer is not None else None,
            accepted=accepted_items,
            ai_backend=backend.name,
            model=backend.model,
            prompt_version=chosen.version(),
            duration_ms=int((time.monotonic() - started) * 1000),
            outcome=outcome,
            error=error,
            called_at=called_at,
        )
    )
    if call_id is None:
        result.records_lost += 1
    if checked is None:
        return _BatchOutcome()

    stored = discarded = 0
    for entry in checked.accepted:
        stored += chosen.store(session, by_sent[entry.item.raw], entry, call_id)
    # Only values whose own item was discarded or missing are charged (8.6).
    for discard in checked.discarded:
        discarded += chosen.fail(session, by_sent[discard.raw])
    for raw in checked.missing:
        discarded += chosen.fail(session, by_sent[raw])
    session.commit()
    return _BatchOutcome(stored, discarded)


def _chunks(groups: Sequence[Group], size: int) -> list[list[Group]]:
    return [list(groups[start : start + size]) for start in range(0, len(groups), size)]


def main(argv: Sequence[str] | None = None, backend_factory=backend_from_env) -> int:
    args = _parse_args(argv)
    fields = FIELD_NAMES if args.field is None else (args.field,)

    try:
        backend = backend_factory()
        backend.check_ready()
    except AiBackendUnavailable as exc:
        print(f"Cannot run: {exc}", file=sys.stderr)
        return 1

    with police_log_lock(engine) as acquired:
        if not acquired:
            print(
                "Another police log job is running (process, reprocess, or geocode). "
                "Try again when it finishes.",
                file=sys.stderr,
            )
            return 1
        call_log = AiCallLog(ai_calls_collection(MongoDB()))
        result = run(backend, call_log, fields=fields, redo=args.redo)

    for summary in result.summaries:
        print(
            f"{summary.field}: {summary.normalized} stored, "
            f"{summary.discarded} discarded, {summary.waiting} still waiting."
        )
    print(f"{result.calls} AI calls, {result.failed_calls} failed.")
    if result.records_lost:
        print(f"{result.records_lost} call records could not be saved to MongoDB.")
    if result.stopped:
        print("The AI backend is logged out or at its limit. Stopped early.")
    return 1 if result.every_call_failed else 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="normalize",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--field", choices=FIELD_NAMES, help="One field, not both.")
    parser.add_argument(
        "--redo",
        action="store_true",
        help="Ask again for AI and rule rows that are not on the current version.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
