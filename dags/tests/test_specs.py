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
        case ["python", "-m", module, *_]:
            assert (REPO_ROOT / spec.cwd / f"{module.replace('.', '/')}.py").is_file()
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


def test_the_police_log_reprocess_is_run_by_hand_and_nothing_triggers_it():
    spec = SPECS_BY_ID["police_log_reprocess"]
    assert spec.schedule is None
    assert all("police_log_reprocess" not in other.triggers for other in SPECS)


def test_the_reprocess_dates_must_look_like_dates_or_be_empty():
    # The values go into a shell command, so Airflow checks their shape first.
    params = SPECS_BY_ID["police_log_reprocess"].params
    pattern = re.compile(params["date_from"]["pattern"])
    assert params["date_to"]["pattern"] == params["date_from"]["pattern"]
    assert all(pattern.fullmatch(ok) for ok in ["", "2026-05-11"])
    assert not any(
        pattern.fullmatch(bad) for bad in ["'; rm -rf ~; '", "05/11/2026", "2026-5-1"]
    )


def test_the_reprocess_dates_are_described_as_a_pair():
    params = SPECS_BY_ID["police_log_reprocess"].params
    for name in ("date_from", "date_to"):
        assert "both" in params[name]["description"].lower()


def test_the_police_log_reprocess_takes_a_date_range_or_everything():
    spec = SPECS_BY_ID["police_log_reprocess"]
    assert set(spec.params) == {"date_from", "date_to"}
    assert "--from '{{ params.date_from }}' --to '{{ params.date_to }}'" in spec.command
    assert "--all" in spec.command
