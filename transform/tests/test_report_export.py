"""The public export end to end: dbt builds the public models, report-gen writes the files.

Reuses the database fixtures and rows from test_dbt_models. report-gen is built with
cargo on first use, so this needs a Rust toolchain.
"""

import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine
from test_dbt_models import DbtProject, dbt, dbt_engine, dispositions_seed, good_rows

# Pytest finds these fixtures by name, so they are imported, not called.
__all__ = ["dbt", "dbt_engine", "dispositions_seed"]

REPO_ROOT = Path(__file__).resolve().parents[2]

INCIDENT_FIELDS = {
    "case_number",
    "reported_at",
    "call_source",
    "incident_type",
    "disposition",
    "location",
    "officer",
    "reference_number",
    "source_url",
    "category",
    "normalized_type",
    "lat",
    "lng",
    "coordinate_precision",
}
ADDRESS_FIELDS = {"raw_address", "normalized_address", "count", "lat", "lng"}
PROPERTY_FIELDS = {
    "parcel_id",
    "location",
    "owner",
    "owner_address",
    "land_use",
    "lot_size_acres",
    "year_built",
    "building_sqft",
    "assessed_land",
    "assessed_building",
    "assessed_total",
    "assessment_year",
    "detail_url",
}
STATS_FIELDS = {"total", "generated_at", "by_type", "by_category", "by_weekday"}


@pytest.fixture(scope="session")
def report_gen() -> Path:
    """The report-gen binary, built once for the session."""
    cargo = shutil.which("cargo")
    assert cargo, "cargo is not on the PATH; the export test needs a Rust toolchain"
    build = subprocess.run(
        [cargo, "build", "--locked", "-p", "report-gen", "--message-format=json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr
    for line in build.stdout.splitlines():
        message: dict[str, Any] = json.loads(line)
        executable = message.get("executable")
        if executable and message.get("target", {}).get("name") == "report-gen":
            return Path(executable)
    raise AssertionError("cargo did not report a report-gen binary")


def database_url(engine: Engine) -> str:
    return engine.url.set(drivername="postgresql").render_as_string(hide_password=False)


def run_report_gen(
    binary: Path, *args: str, database: str | None = None
) -> subprocess.CompletedProcess[str]:
    env = {"PATH": "/usr/bin:/bin"}
    if database:
        env["DATABASE_URL"] = database
    return subprocess.run(
        [str(binary), *args], env=env, capture_output=True, text=True, check=False
    )


def generate(dbt: DbtProject, report_gen: Path, output: Path) -> None:
    """Build the public models over the good rows, then run report-gen into `output`."""
    dbt.seed_rows(good_rows())
    built = dbt.run("build")
    assert built.returncode == 0, built.output
    result = run_report_gen(
        report_gen,
        "--output-dir",
        str(output),
        database=database_url(dbt.engine),
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
def export(dbt: DbtProject, report_gen: Path, tmp_path: Path) -> Iterator[Path]:
    """The five files report-gen writes from the public models over the good rows."""
    output = tmp_path / "data"
    generate(dbt, report_gen, output)
    yield output


def read(directory: Path, name: str) -> Any:
    return json.loads((directory / name).read_text())


def test_every_field_the_site_reads_is_still_there_with_the_new_ones(export):
    incidents = read(export, "incidents.json")
    addresses = read(export, "addresses.json")
    properties = read(export, "properties.json")
    stats = read(export, "stats.json")

    assert {frozenset(row) for row in incidents} == {frozenset(INCIDENT_FIELDS)}
    assert {frozenset(row) for row in addresses} == {frozenset(ADDRESS_FIELDS)}
    assert {frozenset(row) for row in properties} == {frozenset(PROPERTY_FIELDS)}
    assert set(stats) == STATS_FIELDS


def test_the_held_back_fields_are_empty(export):
    incidents = read(export, "incidents.json")
    properties = read(export, "properties.json")

    assert all(row["officer"] is None for row in incidents)
    assert all(row["reference_number"] is None for row in incidents)
    assert all(row["owner"] is None for row in properties)
    assert all(row["owner_address"] is None for row in properties)


def test_only_incidents_in_the_public_window_are_exported(export):
    incidents = read(export, "incidents.json")
    stats = read(export, "stats.json")

    assert sorted(row["case_number"] for row in incidents) == ["26-1001", "26-1002"]
    assert stats["total"] == 2


def test_locations_are_the_public_location(export):
    incidents = {row["case_number"]: row for row in read(export, "incidents.json")}
    addresses = read(export, "addresses.json")

    assert incidents["26-1001"]["location"] == "1200 block of Main St"
    assert (incidents["26-1001"]["lat"], incidents["26-1001"]["lng"]) == (
        43.642,
        -72.251,
    )
    names = {(row["raw_address"], row["normalized_address"]) for row in addresses}
    assert names == {
        ("1200 block of Main St", "1200 block of Main St"),
        ("Main St and Hanover St", "Main St and Hanover St"),
    }


def test_stats_come_from_the_public_set_by_category(export):
    stats = read(export, "stats.json")

    assert {(row["category"], row["count"]) for row in stats["by_category"]} == {
        ("Traffic", 1),
        ("Police", 1),
    }


def test_the_check_passes_on_the_export_and_fails_on_a_leaked_officer(
    export, report_gen, tmp_path
):
    passed = run_report_gen(report_gen, "check", "--dir", str(export))

    leaked = tmp_path / "leaked"
    shutil.copytree(export, leaked)
    incidents = read(leaked, "incidents.json")
    incidents[0]["officer"] = "Smith"
    (leaked / "incidents.json").write_text(json.dumps(incidents))
    failed = run_report_gen(report_gen, "check", "--dir", str(leaked))

    assert passed.returncode == 0, passed.stderr
    assert failed.returncode != 0
    assert "incidents.json: 1 rows have a non-empty officer" in failed.stderr


def test_an_old_export_file_is_replaced_and_other_files_are_left_alone(
    dbt, report_gen, tmp_path
):
    output = tmp_path / "data"
    output.mkdir()
    (output / "incidents.json").write_text('[{"officer": "Smith"}]')
    (output / "notes.txt").write_text("keep me")

    generate(dbt, report_gen, output)

    assert all(row["officer"] is None for row in read(output, "incidents.json"))
    assert (output / "notes.txt").read_text() == "keep me"
    assert run_report_gen(report_gen, "check", "--dir", str(output)).returncode == 0


def test_a_house_number_in_a_public_location_fails_the_check(export, report_gen):
    incidents = read(export, "incidents.json")
    incidents[0]["location"] = "12 Main St"
    (export / "incidents.json").write_text(json.dumps(incidents))

    failed = run_report_gen(report_gen, "check", "--dir", str(export))

    assert failed.returncode != 0
    assert "incidents.json: 1 rows have a house number in location" in failed.stderr
