from pathlib import Path

from scripts.ingest import import_budget_data
from scripts.scrape import download_budget_pdfs

# The agent handoff files live in scripts/data/, which .gitignore covers.
SHARED_DATA_DIR = Path(__file__).parents[1] / "data"


def test_handoff_scripts_use_shared_data_dir():
    assert import_budget_data.DATA_DIR == SHARED_DATA_DIR


def test_budget_pdfs_land_in_shared_data_dir():
    assert download_budget_pdfs.DATA_DIR == SHARED_DATA_DIR / "budgets"
