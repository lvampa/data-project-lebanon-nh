"""What differs between the two normalized fields, behind one interface.

The job asks each field to plan its run (settle what needs no AI, and say what to
send), build a call, check the answer, and store the result. Everything else, the
batching, the call budget, the call records and the exit code, is the same for both,
so it lives in job.py.

This is the only code that reads raw values or writes normalizations (9.9). A row
whose source is `human` is never selected and never written.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from locations.canonical import canonical_address
from postgres.models.address_normalization import AddressNormalization
from postgres.models.incident_type_category import IncidentTypeCategory
from postgres.models.log_entry import LogEntry
from sqlalchemy import case, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from scripts.normalize.checks import (
    Accepted,
    Checked,
    check_incident_types,
    check_locations,
)
from scripts.normalize.prompts import (
    INCIDENT_TYPE_PROMPT_VERSION,
    IncidentTypeAnswer,
    IncidentTypeItem,
    LocationAnswer,
    LocationItem,
    incident_type_prompt,
    location_prompt,
    location_prompt_version,
)
from scripts.normalize.rules import (
    CanonicalLocation,
    PlaceNormalization,
    apply_rules,
    rules_prompt_version,
)

MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Group:
    """Raw values that count as one value. One of them is sent; all of them are filled."""

    raws: tuple[str, ...]

    @property
    def sent(self) -> str:
        return self.raws[0]


@dataclass(frozen=True)
class Plan:
    groups: list[Group]
    # Rows written during planning, by copying a sibling or by a rule.
    settled: int


@dataclass(frozen=True)
class Request:
    prompt: str
    schema: dict[str, Any]
    sent: list[str]


class Field(Protocol):
    name: str

    def can_call(self) -> bool: ...

    def version(self) -> str: ...

    def plan(self, session: Session, redo: bool) -> Plan: ...

    def request(self, groups: Sequence[Group]) -> Request: ...

    def check(self, answer: Any, sent: Sequence[str]) -> Checked[Any]: ...

    def store(
        self,
        session: Session,
        group: Group,
        accepted: Accepted[Any],
        ai_call_id: str | None,
    ) -> int: ...

    def fail(self, session: Session, group: Group) -> int: ...

    def waiting(self, session: Session) -> int: ...


# --- incident types ---


def _folded(name: str) -> str:
    return " ".join(name.lower().split())


class IncidentTypes:
    name = "incident_type"

    def __init__(self) -> None:
        self._names_in_use: list[str] = []

    def can_call(self) -> bool:
        return True

    def version(self) -> str:
        return INCIDENT_TYPE_PROMPT_VERSION

    def plan(self, session: Session, redo: bool) -> Plan:
        raws = _distinct(session, LogEntry.incident_type)
        rows = {
            row.raw_incident_type: row
            for row in session.scalars(select(IncidentTypeCategory))
        }
        redoing = {raw for raw in raws if redo and self._is_redo(rows.get(raw))}
        valued = {
            _folded(raw): row
            for raw, row in rows.items()
            if row.category is not None and raw not in redoing
        }
        self._names_in_use = sorted(
            {r.normalized_type for r in rows.values() if r.normalized_type}
        )

        settled = 0
        to_send: dict[str, list[str]] = defaultdict(list)
        for raw in raws:
            row = rows.get(raw)
            if raw in redoing:
                to_send[_folded(raw)].append(raw)
            elif _needs_value(row, row.category if row else None):
                sibling = valued.get(_folded(raw))
                if sibling is None:
                    to_send[_folded(raw)].append(raw)
                else:
                    self._copy(session, raw, sibling)
                    settled += 1
        return Plan(_groups(to_send), settled)

    def _is_redo(self, row: IncidentTypeCategory | None) -> bool:
        return (
            row is not None
            and row.category is not None
            and row.source == "ai"
            and row.prompt_version != self.version()
        )

    def _copy(self, session: Session, raw: str, sibling: IncidentTypeCategory) -> None:
        self._write(
            session,
            raw,
            category=sibling.category,
            normalized_type=sibling.normalized_type,
            source=sibling.source,
            prompt_version=sibling.prompt_version,
            ai_call_id=sibling.ai_call_id,
            needs_review=sibling.needs_review,
        )

    def request(self, groups: Sequence[Group]) -> Request:
        sent = [group.sent for group in groups]
        return Request(
            incident_type_prompt(sent, self._names_in_use),
            IncidentTypeAnswer.model_json_schema(),
            sent,
        )

    def check(self, answer: Any, sent: Sequence[str]) -> Checked[IncidentTypeItem]:
        return check_incident_types(answer, sent, self._names_in_use)

    def store(
        self,
        session: Session,
        group: Group,
        accepted: Accepted[Any],
        ai_call_id: str | None,
    ) -> int:
        item: IncidentTypeItem = accepted.item
        for raw in group.raws:
            self._write(
                session,
                raw,
                category=item.category,
                normalized_type=item.normalized_type,
                source="ai",
                prompt_version=self.version(),
                ai_call_id=ai_call_id,
                needs_review=accepted.needs_review,
                failed_attempts=0,
            )
        return len(group.raws)

    def fail(self, session: Session, group: Group) -> int:
        for raw in group.raws:
            _charge_attempt(
                session, IncidentTypeCategory, "raw_incident_type", "category", raw
            )
        return len(group.raws)

    def waiting(self, session: Session) -> int:
        rows = {
            row.raw_incident_type: row
            for row in session.scalars(select(IncidentTypeCategory))
        }
        return sum(
            _needs_value(rows.get(raw), rows[raw].category if raw in rows else None)
            for raw in _distinct(session, LogEntry.incident_type)
        )

    def _write(self, session: Session, raw: str, **values: Any) -> None:
        _upsert(session, IncidentTypeCategory, "raw_incident_type", raw, values)


# --- locations ---


class Locations:
    name = "location"

    def __init__(self, streets: Sequence[str]) -> None:
        self._streets = list(streets)
        self._place_codes: dict[str, str | None] = {}

    def can_call(self) -> bool:
        return bool(self._streets)

    def version(self) -> str:
        return location_prompt_version(self._streets)

    def plan(self, session: Session, redo: bool) -> Plan:
        place_codes = _place_codes(session)
        rows = {
            row.raw_address: row
            for row in session.scalars(select(AddressNormalization))
        }
        raws = sorted(place_codes)
        redoing = {raw for raw in raws if redo and _is_redo_location(rows.get(raw))}
        valued = {
            canonical_address(raw): row
            for raw, row in rows.items()
            if row.normalized_address is not None and raw not in redoing
        }

        settled = 0
        by_key: dict[str, list[str]] = defaultdict(list)
        for raw in raws:
            row = rows.get(raw)
            key = canonical_address(raw)
            if raw in redoing:
                by_key[key].append(raw)
            elif _needs_value(row, row.normalized_address if row else None):
                sibling = valued.get(key)
                if sibling is None:
                    by_key[key].append(raw)
                else:
                    self._copy(session, raw, place_codes[raw], sibling)
                    settled += 1

        groups = _groups(by_key)
        result = apply_rules(
            [
                CanonicalLocation(
                    canonical_address(g.sent), _group_place_code(g, place_codes)
                )
                for g in groups
            ],
            self._streets,
            _known_places(
                {raw: row for raw, row in rows.items() if raw not in redoing}
            ),
        )
        by_canonical = {canonical_address(g.sent): g for g in groups}
        for rule in result.settled:
            group = by_canonical[rule.canonical]
            for raw in group.raws:
                if self._already_current(
                    rows.get(raw), rules_prompt_version(), redoing, raw
                ):
                    continue
                self._write(
                    session,
                    raw,
                    place_codes[raw],
                    normalized_address=rule.normalized_address,
                    kind=rule.kind,
                    geocode_query=rule.geocode_query,
                    street=rule.street,
                    source="rule",
                    prompt_version=rules_prompt_version(),
                    ai_call_id=None,
                    needs_review=False,
                )
                settled += 1

        to_send: list[Group] = []
        for leftover in result.leftovers:
            group = by_canonical[leftover.canonical]
            raws_to_send = tuple(
                raw
                for raw in group.raws
                if not self._already_current(
                    rows.get(raw), self.version(), redoing, raw
                )
            )
            if raws_to_send:
                to_send.append(Group(raws_to_send))
        self._place_codes = place_codes
        return Plan(to_send, settled)

    @staticmethod
    def _already_current(
        row: AddressNormalization | None, version: str, redoing: set[str], raw: str
    ) -> bool:
        """A redo skips a row that is already on the version it would get."""
        return raw in redoing and row is not None and row.prompt_version == version

    def _copy(
        self,
        session: Session,
        raw: str,
        place_code: str | None,
        sibling: AddressNormalization,
    ) -> None:
        self._write(
            session,
            raw,
            place_code,
            normalized_address=sibling.normalized_address,
            kind=sibling.kind,
            geocode_query=sibling.geocode_query,
            street=sibling.street,
            source=sibling.source,
            prompt_version=sibling.prompt_version,
            ai_call_id=sibling.ai_call_id,
            needs_review=sibling.needs_review,
        )

    def request(self, groups: Sequence[Group]) -> Request:
        sent = [group.sent for group in groups]
        return Request(
            location_prompt(sent, self._streets),
            LocationAnswer.model_json_schema(),
            sent,
        )

    def check(self, answer: Any, sent: Sequence[str]) -> Checked[LocationItem]:
        return check_locations(answer, sent, self._streets)

    def store(
        self,
        session: Session,
        group: Group,
        accepted: Accepted[Any],
        ai_call_id: str | None,
    ) -> int:
        item: LocationItem = accepted.item
        street = canonical_address(item.street) if item.street.strip() else None
        for raw in group.raws:
            self._write(
                session,
                raw,
                self._place_codes.get(raw),
                normalized_address=item.normalized_address,
                kind=item.kind,
                geocode_query=item.geocode_query or None,
                street=street,
                source="ai",
                prompt_version=self.version(),
                ai_call_id=ai_call_id,
                needs_review=accepted.needs_review,
                failed_attempts=0,
            )
        return len(group.raws)

    def fail(self, session: Session, group: Group) -> int:
        for raw in group.raws:
            _charge_attempt(
                session, AddressNormalization, "raw_address", "normalized_address", raw
            )
        return len(group.raws)

    def waiting(self, session: Session) -> int:
        rows = {
            row.raw_address: row
            for row in session.scalars(select(AddressNormalization))
        }
        return sum(
            _needs_value(
                rows.get(raw), rows[raw].normalized_address if raw in rows else None
            )
            for raw in _place_codes(session)
        )

    def _write(
        self, session: Session, raw: str, place_code: str | None, **values: Any
    ) -> None:
        _upsert(
            session,
            AddressNormalization,
            "raw_address",
            raw,
            {**values, "place_code": place_code},
            cleared_if_changed=_COORDINATES_CLEARED_ON_NEW_ADDRESS,
            changes_on="normalized_address",
        )


# --- shared helpers ---


def _distinct(session: Session, column: Any) -> list[str]:
    return sorted(session.scalars(select(column).where(column.is_not(None)).distinct()))


def _place_codes(session: Session) -> dict[str, str | None]:
    """Every raw location, with the place code its entries print, if any."""
    rows = session.execute(
        select(LogEntry.location, func.max(LogEntry.place_code))
        .where(LogEntry.location.is_not(None))
        .group_by(LogEntry.location)
    ).all()
    return {location: code for location, code in rows if location is not None}


def _group_place_code(
    group: Group, place_codes: Mapping[str, str | None]
) -> str | None:
    return next((place_codes[raw] for raw in group.raws if place_codes[raw]), None)


def _known_places(
    rows: Mapping[str, AddressNormalization],
) -> dict[str, PlaceNormalization]:
    """Place codes that already have a place normalization with no review mark."""
    places: dict[str, PlaceNormalization] = {}
    for row in rows.values():
        if (
            row.place_code
            and row.kind == "place"
            and row.normalized_address
            and not row.needs_review
        ):
            places[row.place_code] = PlaceNormalization(row.normalized_address, "place")
    return places


def _is_redo_location(row: AddressNormalization | None) -> bool:
    return (
        row is not None
        and row.normalized_address is not None
        and row.source in ("ai", "rule")
    )


def _needs_value(row: Any, value: object | None) -> bool:
    """Waiting: no row yet, or a row with no value that has attempts left."""
    if row is None:
        return True
    return (
        value is None and row.failed_attempts < MAX_ATTEMPTS and row.source != "human"
    )


def _groups(by_key: Mapping[str, Sequence[str]]) -> list[Group]:
    return [Group(tuple(sorted(raws))) for _, raws in sorted(by_key.items())]


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


# Coordinates belong to an address. When the address changes they no longer apply.
_COORDINATES_CLEARED_ON_NEW_ADDRESS = {
    "lat": None,
    "lng": None,
    "coordinate_precision": None,
    "geocoded_via": None,
    "geocode_attempts": 0,
}


def _upsert(
    session: Session,
    model: Any,
    key_column: str,
    raw: str,
    values: dict[str, Any],
    cleared_if_changed: Mapping[str, Any] | None = None,
    changes_on: str | None = None,
) -> None:
    """Insert, or update unless a human owns the row.

    `cleared_if_changed` columns are reset when `changes_on` gets a new value.
    """
    now = _now()
    statement = insert(model).values(
        **{key_column: raw}, created_at=now, updated_at=now, **values
    )
    set_ = {**values, "updated_at": now}
    if cleared_if_changed and changes_on:
        changed = getattr(model, changes_on).is_distinct_from(
            getattr(statement.excluded, changes_on)
        )
        for column, reset in cleared_if_changed.items():
            set_[column] = case((changed, reset), else_=getattr(model, column))
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[key_column],
            set_=set_,
            where=model.source.is_distinct_from("human"),
        )
    )


def _charge_attempt(
    session: Session, model: Any, key_column: str, value_column: str, raw: str
) -> None:
    """Count a failed attempt, and mark the value for review at the limit.

    A row that already has a value is left alone: a missed redo must not mark a good
    value for review (8.7)."""
    now = _now()
    statement = insert(model).values(
        **{key_column: raw},
        created_at=now,
        updated_at=now,
        failed_attempts=1,
        needs_review=MAX_ATTEMPTS <= 1,
    )
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[key_column],
            set_={
                "failed_attempts": model.failed_attempts + 1,
                "needs_review": or_(
                    model.needs_review, model.failed_attempts + 1 >= MAX_ATTEMPTS
                ),
                "updated_at": now,
            },
            where=model.source.is_distinct_from("human")
            & getattr(model, value_column).is_(None),
        )
    )
