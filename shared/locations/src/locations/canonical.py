"""The canonical address rules: the one implementation every consumer shares.

Two spellings of the same place reach the same canonical form: case, spacing,
punctuation, suffix and direction spellings, unit spellings, and the joiner of an
intersection. The functions are pure, with no database and no network.

Rule rows record RULES_VERSION. Bump it when street_suffixes.csv or any function
here changes what it returns.
"""

import csv
import re
from importlib import resources

# 2: rule rows now read in title case and carry their street.
RULES_VERSION = "2"

_SEGMENT_JOINERS = re.compile(r"( & | - )")
# A slash joins two streets only between words, not in "N/B" or "S/B".
_SLASH_BETWEEN_WORDS = re.compile(r"([A-Z0-9]{2,})\s*/\s*([A-Z0-9]{2,})")
_UNIT_ID = re.compile(r"^(?:\d+[A-Z]?|[A-Z]|[A-Z]\d+)$")
_HOUSE_NUMBER = re.compile(r"^(\d+[A-Z]?(?:-\d+[A-Z]?)?)\s+(\S.*)$")
_UNIT_DESIGNATORS = frozenset({"APT", "BLDG", "FL", "LOT", "RM", "STE", "UNIT"})
_DESIGNATOR_BEFORE_HASH = re.compile(
    r"\b(APT|APARTMENT|BLDG|BUILDING|FL|FLOOR|LOT|RM|ROOM|STE|SUITE|UNIT)\s*#\s*"
)


def _spellings(kind: str) -> dict[str, str]:
    data = resources.files("locations").joinpath("street_suffixes.csv").read_text()
    rows = csv.DictReader(data.splitlines())
    return {row["variant"]: row["standard"] for row in rows if row["kind"] == kind}


_SUFFIXES = _spellings("suffix")
_DIRECTIONS = _spellings("direction")
_UNITS = {**_spellings("unit"), "#": "UNIT"}

_SUFFIX_FORMS = _SUFFIXES.keys() | set(_SUFFIXES.values())
_DIRECTION_FORMS = _DIRECTIONS.keys() | set(_DIRECTIONS.values())
# A second suffix word that rides along with one, as in "HEATER ROAD EXTENSION".
_SUFFIXES_THAT_FOLLOW_A_SUFFIX = frozenset({"EXT"})


def canonical_address(raw: str) -> str:
    text = raw.upper().replace("'", "").replace("’", "")
    text = re.sub(r"[.,]", " ", text)
    # "UNIT #3" is a unit already; a bare "#3" is a unit too.
    text = _DESIGNATOR_BEFORE_HASH.sub(r"\1 ", text)
    text = re.sub(r"\s*#\s*", " UNIT ", text)
    text = _SLASH_BETWEEN_WORDS.sub(r"\1 & \2", text)
    text = re.sub(r"\bAND\b", "&", text)
    text = re.sub(r"\s*&\s*", " & ", text)
    text = re.sub(r"\s+-\s+", " - ", text)
    text = " ".join(text.split())
    parts = _SEGMENT_JOINERS.split(text)
    # Even positions are address segments; odd positions are the joiners between them.
    return "".join(
        part if index % 2 else _canonical_segment(part)
        for index, part in enumerate(parts)
    )


def split_house_number(canonical: str) -> tuple[str | None, str]:
    """("12", "MAIN ST") for "12 MAIN ST", or (None, "MAIN ST") with no number."""
    match = _HOUSE_NUMBER.match(canonical)
    if match is None:
        return None, canonical
    return match.group(1), match.group(2)


def strip_unit(canonical: str) -> tuple[str, str | None]:
    """("12 MAIN ST", "UNIT 3") for "12 MAIN ST UNIT 3", or the address and None."""
    words = canonical.split()
    if _ends_in_unit(words):
        return " ".join(words[:-2]), f"{words[-2]} {words[-1]}"
    return canonical, None


def _ends_in_unit(words: list[str]) -> bool:
    return (
        len(words) >= 3
        and words[-2] in _UNIT_DESIGNATORS
        and _UNIT_ID.match(words[-1]) is not None
    )


def _canonical_segment(segment: str) -> str:
    words = segment.split()
    unit = _unit_at_the_end(words)
    if unit:
        words = words[:-2]
    words = _with_standard_directions(words)
    words = _with_standard_suffixes(words)
    return " ".join([*words, *unit])


def _unit_at_the_end(words: list[str]) -> list[str]:
    if len(words) < 3 or _UNIT_ID.match(words[-1]) is None:
        return []
    designator = _UNITS.get(words[-2], words[-2])
    if designator not in _UNIT_DESIGNATORS:
        return []
    return [designator, words[-1]]


def _with_standard_directions(words: list[str]) -> list[str]:
    words = list(words)
    if len(words) >= 2 and words[-1] in _DIRECTION_FORMS:
        words[-1] = _DIRECTIONS.get(words[-1], words[-1])
    # A leading direction needs a street name and a suffix after it, so that
    # "WEST LEBANON" is not read as a direction.
    first = 1 if words and words[0][:1].isdigit() else 0
    if len(words) - first >= 3 and words[first] in _DIRECTION_FORMS:
        words[first] = _DIRECTIONS.get(words[first], words[first])
    return words


def _with_standard_suffixes(words: list[str]) -> list[str]:
    words = list(words)
    end = len(words) - 1
    if end >= 1 and words[end] in _DIRECTION_FORMS and words[end - 1] in _SUFFIX_FORMS:
        end -= 1
    if end < 1 or words[end] not in _SUFFIX_FORMS:
        return words
    words[end] = _SUFFIXES.get(words[end], words[end])
    if (
        words[end] in _SUFFIXES_THAT_FOLLOW_A_SUFFIX
        and end >= 2
        and words[end - 1] in _SUFFIX_FORMS
    ):
        words[end - 1] = _SUFFIXES.get(words[end - 1], words[end - 1])
    return words
