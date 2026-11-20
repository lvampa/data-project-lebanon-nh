"""Cells for a CSV that a person opens in a spreadsheet.

A cell that starts with = + - or @ runs as a formula in Excel and Sheets, and the text in
these files comes from city documents and map data. A leading quote makes it text.
"""

from typing import Any

_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def cell(value: Any) -> Any:
    """The value, with text that could run as a formula made safe. Numbers pass through,
    since a negative longitude is not a formula."""
    if isinstance(value, str) and value.startswith(_FORMULA_STARTS):
        return "'" + value
    return value
