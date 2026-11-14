"""The rule pass for locations: settle what code can settle before any AI call.

These are pure functions over canonical locations, the street set, and a map of place
codes that already have a `place` normalization. They make no database or network
call. Whatever they do not settle is a leftover for AI, including a bare street name,
a highway, and any place whose code is unknown.
"""

import re
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass

from locations.canonical import (
    RULES_VERSION,
    split_house_number,
    strip_unit,
)

from scripts.normalize.prompts import LocationKind

_CITY = "Lebanon, NH"
_INTERSECTION_JOINER = " & "


@dataclass(frozen=True)
class CanonicalLocation:
    canonical: str
    place_code: str | None = None


@dataclass(frozen=True)
class PlaceNormalization:
    """What a place code's existing `place` normalization says, with no review mark."""

    normalized_address: str
    kind: LocationKind


@dataclass(frozen=True)
class RuleNormalization:
    canonical: str
    kind: LocationKind
    normalized_address: str
    geocode_query: str
    # A street to fall back on when the full query finds nothing. None for a place.
    street: str | None = None


@dataclass(frozen=True)
class RuleResult:
    settled: list[RuleNormalization]
    leftovers: list[CanonicalLocation]


_DIRECTIONS = frozenset({"N", "S", "E", "W", "NE", "NW", "SE", "SW"})
# Abbreviations that stay upper case: states, "US 4", "PO Box", and the "I" of I-89.
_UPPER_CASE_WORDS = frozenset({"US", "NH", "VT", "ME", "MA", "I", "PO"})
_ORDINAL = re.compile(r"\d+(ST|ND|RD|TH)", re.IGNORECASE)


def display_form(text: str) -> str:
    """How an address reads: "12 MAIN ST" becomes "12 Main St", as the AI writes it.

    Directions stay upper case, ordinals get a lower case suffix ("3rd"), and the
    "and" of an intersection stays lower case.
    """
    return " ".join(_display_word(word) for word in text.split(" "))


def _display_word(word: str) -> str:
    upper = word.upper()
    if upper in _DIRECTIONS or upper in _UPPER_CASE_WORDS:
        return upper
    if word == "and" or not word:
        return word
    if _ORDINAL.fullmatch(word):
        return word.lower()
    return "-".join(_hyphen_part(part) for part in word.split("-"))


def _hyphen_part(part: str) -> str:
    return part.upper() if part.upper() in _UPPER_CASE_WORDS else _capitalized(part)


def _capitalized(part: str) -> str:
    text = part[:1].upper() + part[1:].lower()
    # "O'BRIEN" reads "O'Brien", but "HANNAFORD'S" must not read "Hannaford'S".
    if re.match(r"[A-Z]'[a-z]", text):
        text = text[:2] + text[2:].capitalize()
    # "MCDONALD" reads "McDonald".
    if re.match(r"Mc[a-z]{3,}", text):
        text = text[:2] + text[2:].capitalize()
    return text


def rules_prompt_version() -> str:
    """The version a rule row stores where an AI row stores its prompt version."""
    return f"rules-{RULES_VERSION}"


def apply_rules(
    locations: Iterable[CanonicalLocation],
    streets: Collection[str],
    places: Mapping[str, PlaceNormalization],
) -> RuleResult:
    settled: list[RuleNormalization] = []
    leftovers: list[CanonicalLocation] = []
    for item in locations:
        rule = (
            _address_on_a_listed_street(item, streets)
            or _intersection_of_listed_streets(item, streets)
            or _known_place_code(item, places)
        )
        if rule is None:
            leftovers.append(item)
        else:
            settled.append(rule)
    return RuleResult(settled, leftovers)


def _address_on_a_listed_street(
    item: CanonicalLocation, streets: Collection[str]
) -> RuleNormalization | None:
    """6.15: a house number followed by a street on the street list."""
    address, _unit = strip_unit(item.canonical)
    house_number, street = split_house_number(address)
    if house_number is None or street not in streets:
        return None
    return _rule(item, "address", display_form(address), street=street)


def _intersection_of_listed_streets(
    item: CanonicalLocation, streets: Collection[str]
) -> RuleNormalization | None:
    """6.16: exactly two streets on the street list, joined by and, &, or /."""
    parts = item.canonical.split(_INTERSECTION_JOINER)
    if len(parts) != 2 or not all(part in streets for part in parts):
        return None
    shown = display_form(" and ".join(parts))
    return _rule(item, "intersection", shown, street=parts[0])


def _known_place_code(
    item: CanonicalLocation, places: Mapping[str, PlaceNormalization]
) -> RuleNormalization | None:
    """6.17: a place code that already has a place normalization with no review mark."""
    place = places.get(item.place_code) if item.place_code else None
    if place is None:
        return None
    return _rule(item, place.kind, place.normalized_address)


def _rule(
    item: CanonicalLocation,
    kind: LocationKind,
    normalized_address: str,
    street: str | None = None,
) -> RuleNormalization:
    return RuleNormalization(
        canonical=item.canonical,
        kind=kind,
        normalized_address=normalized_address,
        geocode_query=f"{normalized_address}, {_CITY}",
        street=street,
    )
