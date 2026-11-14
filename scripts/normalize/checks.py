"""Checks on an AI answer. Pure functions: nothing here touches a database or a model.

The answer is never trusted. Each item is validated alone, so one bad item costs only
its own value, and then the set rules run: a value that was not sent, a value that
came back twice, and a value left out. Only discarded and missing values get a failed
attempt; the caller counts those (8.6).
"""

from collections import Counter
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from typing import Any

from locations.canonical import canonical_address
from pydantic import ValidationError

from scripts.normalize.abbreviations import contains_abbreviation
from scripts.normalize.prompts import AnswerItem, IncidentTypeItem, LocationItem


class AnswerOffSchema(ValueError):
    """The answer as a whole is unusable. Nothing is stored and no value is charged."""


@dataclass(frozen=True)
class Accepted[Item]:
    item: Item
    needs_review: bool


@dataclass(frozen=True)
class Discard:
    raw: str
    reason: str


@dataclass(frozen=True)
class Checked[Item]:
    accepted: list[Accepted[Item]]
    discarded: list[Discard]
    # Values that were sent and have no item in the answer at all.
    missing: list[str]
    # Raw values in the answer that were never sent. They belong to no row, so
    # nothing is charged to them; the caller may log them.
    not_sent: list[str]


def check_incident_types(
    answer: Any, sent: Sequence[str], names_in_use: Collection[str]
) -> Checked[IncidentTypeItem]:
    names_by_fold = {_folded(name): name for name in names_in_use}

    def judge(item: IncidentTypeItem) -> Accepted[IncidentTypeItem] | str:
        if contains_abbreviation(item.normalized_type):
            return "abbreviation in the name"
        reused = names_by_fold.get(_folded(item.normalized_type))
        if reused is not None:
            item = item.model_copy(update={"normalized_type": reused})
        return Accepted(item, needs_review=item.unsure)

    return _check(answer, sent, IncidentTypeItem, judge)


def check_locations(
    answer: Any, sent: Sequence[str], streets: Collection[str]
) -> Checked[LocationItem]:
    known_streets = {canonical_address(street) for street in streets}

    def judge(item: LocationItem) -> Accepted[LocationItem] | str:
        # A street that is not on the list can still be right, such as a state road
        # or a neighboring town's street, so it is marked for review, not discarded.
        off_the_list = bool(item.street.strip()) and (
            canonical_address(item.street) not in known_streets
        )
        return Accepted(item, needs_review=item.unsure or off_the_list)

    return _check(answer, sent, LocationItem, judge)


def _check[Item: AnswerItem](
    answer: Any,
    sent: Sequence[str],
    item_model: type[Item],
    judge: Callable[[Item], Accepted[Item] | str],
) -> Checked[Item]:
    raw_items = _items_of(answer)
    sent_values = set(sent)

    parsed: list[Item] = []
    discards: dict[str, str] = {}
    not_sent: list[str] = []
    for raw_item in raw_items:
        try:
            parsed.append(item_model.model_validate(raw_item))
        except ValidationError:
            # An item with no readable raw value cannot be pinned on one value, so
            # that value falls through to "missing".
            raw = raw_item.get("raw") if isinstance(raw_item, dict) else None
            if isinstance(raw, str) and raw in sent_values:
                discards.setdefault(raw, "invalid item")

    counts = Counter(item.raw for item in parsed)
    accepted: list[Accepted[Item]] = []
    for item in parsed:
        raw = item.raw
        if raw not in sent_values:
            if raw not in not_sent:
                not_sent.append(raw)
        elif counts[raw] > 1:
            discards.setdefault(raw, "returned more than once")
        elif raw not in discards:
            verdict = judge(item)
            if isinstance(verdict, str):
                discards[raw] = verdict
            else:
                accepted.append(verdict)

    accepted_raws = {entry.item.raw for entry in accepted}
    missing = [
        value for value in sent if value not in accepted_raws and value not in discards
    ]
    return Checked(
        accepted=accepted,
        discarded=[Discard(raw, reason) for raw, reason in discards.items()],
        missing=missing,
        not_sent=not_sent,
    )


def _items_of(answer: Any) -> list[Any]:
    if not isinstance(answer, dict) or not answer:
        raise AnswerOffSchema("the answer is empty or not a JSON object")
    items = answer.get("items")
    if not isinstance(items, list):
        raise AnswerOffSchema("the answer has no list of items")
    return items


def _folded(name: str) -> str:
    return " ".join(name.lower().split())
