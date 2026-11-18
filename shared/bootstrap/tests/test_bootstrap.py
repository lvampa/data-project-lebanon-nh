import ast
from pathlib import Path
from unittest.mock import Mock, call

import bootstrap
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

# (file, function that must call bootstrap, service name). A function of None means
# the call sits at module level.
ENTRY_POINTS = [
    ("api/main.py", None, "api"),
    ("shared/postgres/migrations/env.py", None, "alembic"),
    ("scripts/migrate.py", "main", "migrate"),
    ("scripts/normalize/job.py", "main", "normalize"),
    ("scripts/normalize/geocode.py", "main", "geocode"),
    ("scripts/ingest/import_budget_data.py", "main", "import-budget-data"),
    ("scripts/scrape/download_budget_pdfs.py", "main", "download-budget-pdfs"),
    ("scripts/scrape/scrape_civicclerk.py", "run", "scrape-civicclerk"),
    ("scripts/scrape/scrape_llcs.py", "run", "scrape-llcs"),
    ("scrapers/run_process_urls.py", "main", "process-urls"),
    ("scrapers/extensions.py", "__init__", "scrapers"),
    ("scrapers/maintenance/police_logs.py", "main", "police-logs"),
    ("scrapers/maintenance/reprocess_police_logs.py", "main", "reprocess-police-logs"),
    ("scrapers/maintenance/postgres_backup.py", "main", "postgres-backup"),
    ("scrapers/maintenance/mongo_backup.py", "main", "mongo-backup"),
]


def test_bootstrap_loads_dotenv_before_configuring_logfire(bootstrap_mocks):
    order = Mock()
    order.attach_mock(bootstrap_mocks.load_dotenv, "load_dotenv")
    order.attach_mock(bootstrap_mocks.configure, "configure")

    bootstrap.bootstrap("demo")

    assert order.mock_calls == [call.load_dotenv(), call.configure(service_name="demo")]


def test_second_call_does_nothing(bootstrap_mocks):
    bootstrap.bootstrap("first")
    bootstrap.bootstrap("second")

    bootstrap_mocks.load_dotenv.assert_called_once()
    bootstrap_mocks.configure.assert_called_once_with(service_name="first")


def _calls_bootstrap_with(body: list[ast.stmt], service_name: str) -> bool:
    for statement in body:
        for node in ast.walk(statement):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "bootstrap"
                and [a.value for a in node.args if isinstance(a, ast.Constant)]
                == [service_name]
            ):
                return True
    return False


@pytest.mark.parametrize(("path", "function", "service_name"), ENTRY_POINTS)
def test_entry_point_calls_bootstrap(path, function, service_name):
    tree = ast.parse((REPO_ROOT / path).read_text())
    if function is None:
        body = tree.body
    else:
        matches = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
            and n.name == function
        ]
        assert matches, f"{path} has no {function}()"
        body = [s for m in matches for s in m.body]

    assert _calls_bootstrap_with(body, service_name)
