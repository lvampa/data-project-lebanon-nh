"""Write seeds/dispositions.csv from the parser's disposition list before each dbt build.

The list stays in one place, the parser, and the data check in
tests/assert_no_raw_type_ends_with_disposition.sql reads this seed.

Run from the repo root: uv run python transform/write_disposition_seed.py
"""

from pathlib import Path

SEED_PATH = Path(__file__).parent / "seeds" / "dispositions.csv"


def write_disposition_seed(dispositions: list[str], path: Path = SEED_PATH) -> None:
    """Write one `disposition` column, one row per disposition, sorted."""
    raise NotImplementedError("PR 7 task 19")


if __name__ == "__main__":
    # TODO(PR 3 task 7): import the disposition list from the module PR 3 moves it to.
    raise NotImplementedError("PR 7 task 19: needs PR 3's disposition module")
