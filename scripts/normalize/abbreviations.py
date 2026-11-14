"""Dispatch abbreviations that must not appear in a normalized incident type name.

A resident reading the website should never meet "MV" or "BOL". The model is told to
spell them out, and the checks discard a name that still contains one as a whole word.

This is a starting list. When a discard shows a new abbreviation, add it here.
"""

import re

DISPATCH_ABBREVIATIONS = frozenset(
    {"ATL", "BOL", "DV", "FD", "MV", "MVA", "MVC", "PD", "UTL"}
)

_WHOLE_WORD = re.compile(
    r"\b(?:" + "|".join(sorted(DISPATCH_ABBREVIATIONS)) + r")\b", re.IGNORECASE
)


def contains_abbreviation(name: str) -> bool:
    return _WHOLE_WORD.search(name) is not None
