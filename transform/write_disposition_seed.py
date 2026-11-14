"""Write seeds/dispositions.csv from the parser's disposition list before each dbt build.

The list stays in one place, the parser, and the data check in
data_tests/assert_no_raw_type_ends_with_disposition.sql reads this seed.

Run from the repo root: uv run python transform/write_disposition_seed.py
"""

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = Path(__file__).parent / "seeds" / "dispositions.csv"


def parser_dispositions() -> list[str]:
    # The scrapers code imports as top-level packages from scrapers/, not as an
    # installed package, so the directory goes on the path first.
    sys.path.insert(0, str(REPO_ROOT / "scrapers"))
    from parsers.dispositions import _DISPOSITIONS

    return list(_DISPOSITIONS)


def write_disposition_seed(dispositions: list[str], path: Path = SEED_PATH) -> None:
    """Write one `disposition` column, one row per disposition, sorted."""
    path.parent.mkdir(exist_ok=True)
    with path.open("w", newline="") as seed:
        writer = csv.writer(seed)
        writer.writerow(["disposition"])
        writer.writerows([d] for d in sorted(dispositions))


if __name__ == "__main__":
    write_disposition_seed(parser_dispositions())
    print(f"Wrote {SEED_PATH.relative_to(REPO_ROOT)}")
