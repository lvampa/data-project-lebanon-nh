"""Cells for a CSV that a person opens in a spreadsheet.

A cell that starts with = + - or @ runs as a formula in Excel and Sheets, and the text in
these files comes from city documents and map data. A leading quote makes it text.
"""

from typing import Any

FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def cell(value: Any) -> Any:
    """The value, with text that could run as a formula made safe. Numbers pass through,
    since a negative longitude is not a formula."""
    if isinstance(value, str) and value.startswith(FORMULA_STARTS):
        return "'" + value
    return value


def uncell(value: str) -> str:
    """Undo the quote `cell` adds, so text that starts with a formula character matches
    again after a round trip through a file."""
    if value.startswith("'") and value[1:].startswith(FORMULA_STARTS):
        return value[1:]
    return value
