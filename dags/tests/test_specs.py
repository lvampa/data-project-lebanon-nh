import re
from pathlib import Path

import pytest

from dags.specs import SPECS

REPO_ROOT = Path(__file__).resolve().parents[2]
SPECS_BY_ID = {spec.dag_id: spec for spec in SPECS}

# minute, hour, day of month, month, day of week
CRON_FIELD_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
CRON_ITEM = re.compile(r"^(\*|(\d+)(?:-(\d+))?)(?:/(\d+))?$")


def is_valid_cron(expression: str) -> bool:
    fields = expression.split()
    if len(fields) != len(CRON_FIELD_RANGES):
        return False
    for field, (low, high) in zip(fields, CRON_FIELD_RANGES, strict=True):
        for item in field.split(","):
            match = CRON_ITEM.match(item)
            if not match:
                return False
            numbers = [int(n) for n in match.group(2, 3) if n is not None]
            if any(n < low or n > high for n in numbers):
                return False
    return True


def downstream_of(dag_id: str) -> set[str]:
    reached: set[str] = set()
    pending = list(SPECS_BY_ID[dag_id].triggers)
    while pending:
        target = pending.pop()
        if target not in reached:
            reached.add(target)
            pending.extend(SPECS_BY_ID[target].triggers)
    return reached


def spider_names() -> set[str]:
    spider_files = (REPO_ROOT / "scrapers" / "spiders").glob("*.py")
    source = "\n".join(path.read_text() for path in spider_files)
    return set(re.findall(r'^    name = "(\w+)"$', source, re.MULTILINE))


def test_dag_ids_are_unique():
    assert len(SPECS_BY_ID) == len(SPECS)


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.dag_id)
def test_schedule_is_cron_or_none(spec):
    assert spec.schedule is None or is_valid_cron(spec.schedule)


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.dag_id)
def test_command_target_exists(spec):
    match spec.command.split():
        case ["scrapy", "crawl", spider, *_]:
            assert spider in spider_names()
        case ["python", script, *_]:
            assert (REPO_ROOT / spec.cwd / script).is_file()
        case _:
            pytest.fail(f"unrecognized command: {spec.command}")


def test_triggers_name_known_dags():
    for spec in SPECS:
        assert set(spec.triggers) <= SPECS_BY_ID.keys(), spec.dag_id


def test_triggered_dags_have_no_schedule():
    triggered = {target for spec in SPECS for target in spec.triggers}
    for dag_id in triggered:
        assert SPECS_BY_ID[dag_id].schedule is None, dag_id


def test_llc_lookup_runs_after_vgsi_property():
    assert "llc_lookup" in SPECS_BY_ID["vgsi_property"].triggers


def test_every_indexed_source_leads_to_elasticsearch_sync():
    # Budget documents are not indexed; budget data reaches Elasticsearch
    # through scripts/ingest, which no DAG runs.
    not_indexed = {"sync_elasticsearch", "budget_discovery"}
    for spec in SPECS:
        if spec.dag_id not in not_indexed:
            assert "sync_elasticsearch" in downstream_of(spec.dag_id), spec.dag_id
