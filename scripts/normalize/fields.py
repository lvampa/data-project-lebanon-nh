"""What differs between the two normalized fields, behind one interface.

The job asks each field to plan its run (settle what needs no AI, and say what to
send), build a call, check the answer, and store the result. Everything else, the
batching, the call budget, the call records and the exit code, is the same for both,
so it lives in job.py.

This is the only code that reads raw values or writes normalizations. A row
whose source is `human` is never selected and never written.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from locations.canonical import canonical_address, canonical_crossing, crossing_key
from postgres import utc_now
from postgres.models.address_normalization import AddressNormalization
from postgres.models.incident_type_category import IncidentTypeCategory
from postgres.models.log_entry import LogEntry
from sqlalchemy import case, func, or_, select, update
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
    LOCATION_PROMPT_VERSION,
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

    def entries(self, session: Session, raws: Sequence[str]) -> int:
        """How many log entries carry any of these raw values."""
        ...


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

    def entries(self, session: Session, raws: Sequence[str]) -> int:
        return _entries_with(session, LogEntry.incident_type, raws)

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
        self._crossings: dict[str, str] | None = None
        # The session the run was planned with. The job commits after every batch, so
        # each request reads the names the earlier batches stored.
        self._session: Session | None = None

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
                    # A house number on a listed street, or two listed streets, names
                    # no one.
                    names_person=False,
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
        self._session = session
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
            names_person=sibling.names_person,
            source=sibling.source,
            prompt_version=sibling.prompt_version,
            ai_call_id=sibling.ai_call_id,
            needs_review=sibling.needs_review,
        )

    def request(self, groups: Sequence[Group]) -> Request:
        sent = [group.sent for group in groups]
        known = (
            names_in_use(self._session, sent, self._streets)
            if self._session is not None
            else []
        )
        return Request(
            location_prompt(sent, self._streets, known),
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
            if _has_own_pin(session, raw):
                self._keep_named_pin(session, raw, item, accepted, ai_call_id)
                continue
            self._write(
                session,
                raw,
                self._place_codes.get(raw),
                normalized_address=item.normalized_address,
                kind=item.kind,
                geocode_query=item.geocode_query or None,
                street=street,
                names_person=item.names_person,
                source="ai",
                prompt_version=self.version(),
                ai_call_id=ai_call_id,
                needs_review=accepted.needs_review,
                failed_attempts=0,
            )
        return len(group.raws)

    def _keep_named_pin(
        self,
        session: Session,
        raw: str,
        item: LocationItem,
        accepted: Accepted[Any],
        ai_call_id: str | None,
    ) -> None:
        """A hand-placed or researched pin stays on its own name, as a human row's does.
        The privacy flag and the version still follow the answer, and a different answer
        marks the row for a person to merge."""
        row = session.scalars(
            select(AddressNormalization).where(AddressNormalization.raw_address == raw)
        ).one()
        session.execute(
            update(AddressNormalization)
            .where(AddressNormalization.id == row.id)
            .values(
                names_person=item.names_person,
                prompt_version=self.version(),
                ai_call_id=ai_call_id,
                needs_review=(
                    row.needs_review
                    or accepted.needs_review
                    or row.normalized_address != item.normalized_address
                ),
                updated_at=utc_now(),
            )
        )

    def fail(self, session: Session, group: Group) -> int:
        for raw in group.raws:
            _charge_attempt(
                session, AddressNormalization, "raw_address", "normalized_address", raw
            )
        return len(group.raws)

    def entries(self, session: Session, raws: Sequence[str]) -> int:
        return _entries_with(session, LogEntry.location, raws)

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
        if values.get("kind") == "intersection" and values.get("normalized_address"):
            # Only an intersection is a crossing: "Wright and Sons, Main St" is a place.
            shown = self._crossing_text(session, values["normalized_address"])
            values = {
                **values,
                "normalized_address": shown,
                "geocode_query": f"{shown}, Lebanon, NH",
            }
        _upsert(
            session,
            AddressNormalization,
            "raw_address",
            raw,
            {**values, "place_code": place_code},
            cleared_if_changed=_COORDINATES_CLEARED_ON_NEW_ADDRESS,
            changes_on="normalized_address",
        )

    def _crossing_text(self, session: Session, normalized: str) -> str:
        """The text a crossing is stored as: its legs in order, in the spelling the
        crossing already has. A `human` row's spelling comes first, then the lowest id, so
        a new spelling lands on the text the rest already share. The backfill picks the
        most-used spelling instead, and the two agree once every row has the same text."""
        if self._crossings is None:
            self._crossings = {}
            rows = session.execute(
                select(AddressNormalization.normalized_address)
                .where(
                    AddressNormalization.kind == "intersection",
                    AddressNormalization.normalized_address.is_not(None),
                )
                .order_by(
                    (AddressNormalization.source == "human").desc(),
                    AddressNormalization.id,
                )
            )
            for (stored,) in rows:
                key = crossing_key(stored) if stored else None
                if stored and key is not None:
                    self._crossings.setdefault(key, stored)
        ordered = canonical_crossing(normalized)
        key = crossing_key(ordered)
        if key is None:
            return ordered
        return self._crossings.setdefault(key, ordered)


# --- shared helpers ---


def _entries_with(session: Session, column: Any, raws: Sequence[str]) -> int:
    return (
        session.scalar(
            select(func.count()).select_from(LogEntry).where(column.in_(raws))
        )
        or 0
    )


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


# How many place names one location prompt carries.
KNOWN_PLACE_LIMIT = 100
# A pin a person placed or a researcher found. The name it sits on is kept with it.
_PERSON_PLACED = ("manual", "research")


def _has_own_pin(session: Session, raw: str) -> bool:
    return bool(
        session.scalar(
            select(func.count())
            .select_from(AddressNormalization)
            .where(
                AddressNormalization.raw_address == raw,
                AddressNormalization.normalized_address.is_not(None),
                AddressNormalization.source != "human",
                AddressNormalization.geocoded_via.in_(_PERSON_PLACED),
            )
        )
    )


def names_in_use(
    session: Session, raws: Sequence[str], streets: Sequence[str]
) -> list[str]:
    """Place names the AI may reuse for these raw values, most shared first.

    A name is offered when its street appears in a raw value, or its first word is a word
    of one, since many parts of a place are written with no street. Only names the AI
    would give again are offered: the current location version, or a rule row. A person's
    text and a human row's text are never offered."""
    canonical = [canonical_address(raw) for raw in raws]
    padded = [f" {text} " for text in canonical]
    mentioned = {
        street for street in streets if any(f" {street} " in p for p in padded)
    }
    words = {
        w for text in canonical for w in text.split() if len(w) >= 4 and w.isalpha()
    }
    rows = session.execute(
        select(
            AddressNormalization.normalized_address,
            AddressNormalization.street,
            func.count(),
        )
        .where(
            AddressNormalization.kind == "place",
            AddressNormalization.normalized_address.is_not(None),
            AddressNormalization.names_person.is_(False),
            AddressNormalization.source != "human",
            or_(
                AddressNormalization.prompt_version.like(f"{LOCATION_PROMPT_VERSION}%"),
                (AddressNormalization.source == "rule")
                & (AddressNormalization.prompt_version == rules_prompt_version()),
            ),
        )
        .group_by(AddressNormalization.normalized_address, AddressNormalization.street)
    ).all()
    shared: dict[str, int] = defaultdict(int)
    for name, street, count in rows:
        if name is None:
            continue
        first_word = next(iter(canonical_address(name).split()), "")
        if street in mentioned or first_word in words:
            shared[name] += count
    ranked = sorted(shared, key=lambda name: (-shared[name], name))
    return ranked[:KNOWN_PLACE_LIMIT]


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


# Coordinates belong to an address. When the address changes they no longer apply.
_COORDINATES_CLEARED_ON_NEW_ADDRESS = {
    "lat": None,
    "lng": None,
    "coordinate_precision": None,
    "geocoded_via": None,
    "osm_ref": None,
    "geocode_source_url": None,
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
    now = utc_now()
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
    value for review."""
    now = utc_now()
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
