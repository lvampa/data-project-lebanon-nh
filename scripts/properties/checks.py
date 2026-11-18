"""The quality checks that gate a property build, and the thresholds they use.

Each check is a pure function of the parsed records, so it can be tested alone. The
thresholds are named here, to be tuned after the first full build.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from scripts.models.property import PropertyRecord

# Lebanon has a few thousand parcels. A first build with fewer is a partial crawl.
FIRST_BUILD_FLOOR = 3000
# How far the parcel count may move from the table it replaces.
MAX_COUNT_CHANGE = 0.10
# The most parcels that may lack one of the core fields.
MAX_EMPTY_SHARE = 0.05
CORE_FIELDS = ("location", "owner", "mblu", "assessed_total")
# The least share of parcels that must have a sale.
MIN_PARCELS_WITH_SALES = 0.5


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


def check_count(parsed: int, current: int) -> CheckResult:
    if current == 0:
        return CheckResult(
            "count",
            parsed >= FIRST_BUILD_FLOOR,
            f"{parsed} parcels, and a first build needs {FIRST_BUILD_FLOOR}",
        )
    change = abs(parsed - current) / current
    return CheckResult(
        "count",
        change <= MAX_COUNT_CHANGE,
        f"{parsed} parcels against {current} now, {change:.1%} apart "
        f"(limit {MAX_COUNT_CHANGE:.0%})",
    )


def check_core_fields(records: Sequence[PropertyRecord]) -> CheckResult:
    if not records:
        return CheckResult("core fields", False, "no parcels")
    shares = {
        field: sum(not getattr(record, field) for record in records) / len(records)
        for field in CORE_FIELDS
    }
    return CheckResult(
        "core fields",
        all(share <= MAX_EMPTY_SHARE for share in shares.values()),
        "empty: "
        + ", ".join(f"{field} {share:.1%}" for field, share in shares.items())
        + f" (limit {MAX_EMPTY_SHARE:.0%})",
    )


def check_unique_mblu(records: Sequence[PropertyRecord]) -> CheckResult:
    counts = Counter(record.mblu for record in records if record.mblu)
    repeated = sorted(mblu for mblu, count in counts.items() if count > 1)
    return CheckResult(
        "key",
        not repeated,
        f"{len(repeated)} mblu shared by parcels"
        + (f", such as {repeated[:3]}" if repeated else ""),
    )


def check_sales(records: Sequence[PropertyRecord]) -> CheckResult:
    if not records:
        return CheckResult("sales", False, "no parcels")
    share = sum(bool(record.sales) for record in records) / len(records)
    return CheckResult(
        "sales",
        share >= MIN_PARCELS_WITH_SALES,
        f"{share:.1%} of parcels have a sale (needs {MIN_PARCELS_WITH_SALES:.0%})",
    )


def run_checks(records: Sequence[PropertyRecord], current: int) -> list[CheckResult]:
    return [
        check_count(len(records), current),
        check_core_fields(records),
        check_unique_mblu(records),
        check_sales(records),
    ]
