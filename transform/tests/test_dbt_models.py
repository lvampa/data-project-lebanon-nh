"""The dbt models and data checks, built against a real Postgres database.

Each data check gets one bad case that must fail the build, so a check that stops
catching anything shows up here (design.md, Testing strategy; requirement 14).

dbt runs in its own process and reads committed rows, so these tests can't use the
rolled-back `db_connection`. They get their own database, `app_dbt_test`, migrated to
head at the start of the session and dropped at the end. It is never `app_test`: views
over `log_entries` there would block the migration tests from dropping columns.

Checks on rows that come from the source tables are tested with a bad source row.
The public models write the held-back fields as empty literals, so no source row can
break those checks; they are tested by swapping in a public view that leaks the field,
the regression each check exists to catch.
"""

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest
from postgres.models import (
    AddressNormalization,
    IncidentTypeCategory,
    LogEntry,
    Property,
)
from postgres_testing.plugin import (
    _create_database_if_missing,
    _upgrade_to_head,
    is_test_database,
)
from sqlalchemy import URL, Engine, create_engine, insert, text

DBT_TEST_DATABASE = os.environ.get("TEST_DBT_POSTGRES_DB", "app_dbt_test")
PROJECT_DIR = Path(__file__).resolve().parents[1]
DISPOSITIONS_SEED = PROJECT_DIR / "seeds" / "dispositions.csv"
SOURCE_TABLES = (LogEntry, IncidentTypeCategory, AddressNormalization, Property)
NOW = datetime(2026, 11, 2, 12, 0)

# The newest log date is 2026-11-01, so the public window is 2026-08-04 to 2026-11-01.
NEWEST_LOG_DATE = date(2026, 11, 1)
JUST_OUTSIDE_WINDOW = date(2026, 8, 3)


# --- Fixtures ---------------------------------------------------------------------


@dataclass(frozen=True)
class DbtResult:
    returncode: int
    statuses: dict[str, tuple[str, int | None]]
    output: str

    def status(self, test_name: str) -> tuple[str, int | None]:
        """The status and failure count of the one test whose name starts so."""
        matches = [
            value
            for unique_id, value in self.statuses.items()
            if unique_id.split(".")[2] == test_name
            or unique_id.split(".")[2].startswith(test_name + "_")
        ]
        assert len(matches) == 1, f"{test_name}: {len(matches)} matches\n{self.output}"
        return matches[0]


@dataclass(frozen=True)
class DbtProject:
    engine: Engine
    target_dir: Path

    def run(self, *args: str) -> DbtResult:
        completed = subprocess.run(
            [str(Path(sys.executable).parent / "dbt"), *args, *self._flags()],
            cwd=PROJECT_DIR,
            env=self._env(),
            capture_output=True,
            text=True,
            check=False,
        )
        return DbtResult(
            completed.returncode, self._statuses(), completed.stdout + completed.stderr
        )

    def seed_rows(self, rows: dict[type, list[dict[str, Any]]]) -> None:
        with self.engine.begin() as connection:
            names = ", ".join(model.__tablename__ for model in SOURCE_TABLES)
            connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
            # One insert per row: the rows set different columns, and a bulk insert
            # needs every row to have the same keys.
            for model, model_rows in rows.items():
                for row in model_rows:
                    connection.execute(insert(model.__table__).values(**row))

    def replace_view(self, name: str, select_sql: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(text(f"DROP VIEW IF EXISTS marts.{name} CASCADE"))
            connection.execute(text(f"CREATE VIEW marts.{name} AS {select_sql}"))

    def _flags(self) -> list[str]:
        return [
            "--project-dir",
            str(PROJECT_DIR),
            "--profiles-dir",
            str(PROJECT_DIR),
            "--target-path",
            str(self.target_dir),
            "--log-path",
            str(self.target_dir / "logs"),
        ]

    def _env(self) -> dict[str, str]:
        url = self.engine.url
        return {
            **os.environ,
            "POSTGRES_HOST": url.host or "localhost",
            "POSTGRES_PORT": str(url.port or 5432),
            "POSTGRES_USER": url.username or "",
            "POSTGRES_PASSWORD": url.password or "",
            "POSTGRES_DB": DBT_TEST_DATABASE,
            "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
        }

    def _statuses(self) -> dict[str, tuple[str, int | None]]:
        results_file = self.target_dir / "run_results.json"
        if not results_file.exists():
            return {}
        results = json.loads(results_file.read_text())["results"]
        return {r["unique_id"]: (r["status"], r.get("failures")) for r in results}


@pytest.fixture(scope="session")
def dbt_engine(test_engine: Engine) -> Iterator[Engine]:
    """A migrated `app_dbt_test`, dropped when the session ends."""
    if not is_test_database(DBT_TEST_DATABASE):
        pytest.exit(f"Refusing to run dbt tests against {DBT_TEST_DATABASE!r}.")
    url: URL = test_engine.url.set(database=DBT_TEST_DATABASE)
    _drop_database(url)
    _create_database_if_missing(url)
    engine = create_engine(url)
    try:
        _upgrade_to_head(engine)
        yield engine
    finally:
        engine.dispose()
        _drop_database(url)


@pytest.fixture(scope="session")
def dispositions_seed() -> None:
    """The real seed, generated from the parser's list, as before every build."""
    subprocess.run(
        [sys.executable, str(PROJECT_DIR / "write_disposition_seed.py")], check=True
    )


@pytest.fixture
def dbt(
    dbt_engine: Engine, dispositions_seed: None, tmp_path: Path
) -> Iterator[DbtProject]:
    project = DbtProject(dbt_engine, tmp_path)
    yield project
    with dbt_engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS marts CASCADE"))


def _drop_database(url: URL) -> None:
    maintenance = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        with maintenance.connect() as connection:
            connection.execute(
                text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)')
            )
    finally:
        maintenance.dispose()


# --- Rows ---------------------------------------------------------------------------


def entry(case_number: str, log_date: date = NEWEST_LOG_DATE, **values: Any) -> dict:
    return {
        "source_url": "https://example.test/log.pdf",
        "case_number": case_number,
        "log_date": log_date,
        "created_at": NOW,
        "updated_at": NOW,
        **values,
    }


def category(raw: str, value: str) -> dict:
    return {
        "raw_incident_type": raw,
        "category": value,
        "created_at": NOW,
        "updated_at": NOW,
    }


def location(raw: str, normalized: str, lat: float, lng: float, **values: Any) -> dict:
    return {
        "raw_address": raw,
        "normalized_address": normalized,
        "lat": lat,
        "lng": lng,
        "geocoded_via": "nominatim",
        "created_at": NOW,
        "updated_at": NOW,
        **values,
    }


def good_rows() -> dict[type, list[dict[str, Any]]]:
    """Rows every check passes on, including the edges the checks look at."""
    return {
        LogEntry: [
            entry(
                "26-1001",
                incident_type="MV Complaint",
                location="1234 MAIN ST",
                officer="Smith",
                reference_number="R-1",
            ),
            entry(
                "26-1002",
                incident_type="Welfare Check",
                location="MAIN ST / HANOVER ST",
                officer="Jones",
            ),
            entry(
                "26-0900",
                JUST_OUTSIDE_WINDOW,
                incident_type="Alarm",
                location="45 HANOVER ST",
                officer="Smith",
            ),
            entry("26-0902", parse_error=True, incident_type="garbled"),
        ],
        IncidentTypeCategory: [
            category("MV Complaint", "Traffic"),
            category("Welfare Check", "Police"),
        ],
        AddressNormalization: [
            location(
                "1234 MAIN ST",
                "1234 Main St",
                43.6421567,
                -72.2512345,
                kind="address",
                street="MAIN ST",
                coordinate_precision="exact",
                source="ai",
            ),
            location(
                "MAIN ST / HANOVER ST",
                "Main St and Hanover St",
                43.6431,
                -72.2501,
                kind="intersection",
                coordinate_precision="exact",
                source="rule",
            ),
        ],
        Property: [
            {
                "parcel_id": "1-2-3",
                "location": "1234 MAIN ST",
                "owner": "JANE RESIDENT",
                "owner_address": "1234 MAIN ST, LEBANON NH",
                "created_at": NOW,
                "updated_at": NOW,
            },
        ],
    }


def with_rows(model: type, *extra: dict) -> dict[type, list[dict[str, Any]]]:
    rows = good_rows()
    rows[model] = [*rows[model], *extra]
    return rows


# --- Tests --------------------------------------------------------------------------


def test_good_rows_pass_every_check(dbt):
    dbt.seed_rows(good_rows())

    result = dbt.run("build")

    assert result.returncode == 0, result.output
    assert all(status in ("pass", "success") for status, _ in result.statuses.values())


@pytest.mark.parametrize(
    ("rows", "check"),
    [
        pytest.param(
            with_rows(
                AddressNormalization, location("1 FAR RD", "1 Far Rd", 40.0, -72.25)
            ),
            "assert_locations_inside_city_bounds",
            id="14.2-coordinates-outside-the-city",
        ),
        pytest.param(
            with_rows(LogEntry, entry("26-1003", incident_type="Alarm Investigated")),
            "assert_no_raw_type_ends_with_disposition",
            id="14.3-type-ends-with-a-disposition",
        ),
        pytest.param(
            with_rows(IncidentTypeCategory, category("Alarm", "Weird")),
            "accepted_values_stg_incident_types_category",
            id="14.4-category-outside-the-five",
        ),
    ],
)
def test_a_bad_source_row_fails_its_check(dbt, rows, check):
    dbt.seed_rows(rows)

    result = dbt.run("build")

    assert result.returncode != 0
    # 14.6: the build names the check and counts the rows that failed it.
    assert result.status(check) == ("fail", 1), result.output


def test_coordinates_set_by_hand_may_be_outside_the_city(dbt):
    dbt.seed_rows(
        with_rows(
            AddressNormalization,
            location("1 FAR RD", "1 Far Rd", 40.0, -72.25, geocoded_via="manual"),
        )
    )

    result = dbt.run("build", "--select", "+assert_locations_inside_city_bounds")

    assert result.status("assert_locations_inside_city_bounds") == ("pass", 0)


@pytest.mark.parametrize(
    ("view", "leaky_select", "check"),
    [
        pytest.param(
            "public_incidents",
            "select case_number, officer, reference_number from marts.incidents",
            "assert_public_incidents_officer_empty",
            id="14.5-officer-in-the-public-set",
        ),
        pytest.param(
            "public_incidents",
            "select case_number, log_date from marts.incidents",
            "assert_public_incidents_inside_window",
            id="14.5-incident-outside-the-window",
        ),
        pytest.param(
            "public_incidents",
            "select case_number, normalized_address as location, lat, lng,"
            " 'address'::text as location_kind"
            " from marts.incidents where case_number = '26-1001'",
            "assert_public_locations_at_block_level",
            id="14.5-house-number-in-the-public-set",
        ),
        pytest.param(
            "public_incidents",
            "select case_number, '1200 block of Main St'::text as location, lat, lng,"
            " 'address'::text as location_kind"
            " from marts.incidents where case_number = '26-1001'",
            "assert_public_locations_at_block_level",
            id="14.5-exact-coordinates-in-the-public-set",
        ),
        *[
            pytest.param(
                "public_incidents",
                f"select case_number, '{leak}'::text as location,"
                " round(lat::numeric, 3)::float8 as lat,"
                " round(lng::numeric, 3)::float8 as lng,"
                " 'address'::text as location_kind"
                " from marts.incidents where case_number = '26-1001'",
                "assert_public_locations_at_block_level",
                id=f"14.5-address-text-{leak}",
            )
            for leak in (
                "Rear 12 Main St",
                "Main St 12",
                "Main St Lot 5",
                "Main St Apt 3 B",
            )
        ],
        pytest.param(
            "public_incidents",
            "select case_number, 'Smith residence, 12 Main St'::text as location,"
            " 'place'::text as location_kind"
            " from marts.incidents where case_number = '26-1001'",
            "assert_public_non_address_has_no_house_number",
            id="house-number-in-a-place",
        ),
        pytest.param(
            "public_properties",
            "select parcel_id, owner, owner_address from public.properties",
            "assert_public_properties_have_no_owner",
            id="14.7-owner-in-the-public-parcels",
        ),
        pytest.param(
            "incidents",
            "select * from marts.stg_log_entries"
            " union all select * from marts.stg_log_entries where case_number = '26-1001'",
            "unique_incidents_case_number",
            id="14.4-case-number-twice",
        ),
    ],
)
def test_a_leaky_model_fails_its_check(dbt, view, leaky_select, check):
    dbt.seed_rows(good_rows())
    assert dbt.run("run").returncode == 0
    dbt.replace_view(view, leaky_select)

    result = dbt.run("test", "--select", check)

    assert result.returncode != 0
    assert result.status(check)[0] == "fail", result.output
    assert result.status(check)[1] >= 1


def test_the_public_set_holds_no_held_back_values(dbt):
    dbt.seed_rows(good_rows())
    assert dbt.run("run").returncode == 0

    with dbt.engine.connect() as connection:
        incidents = connection.execute(
            text(
                "select case_number, officer, reference_number, location, lat, lng"
                " from marts.public_incidents order by case_number"
            )
        ).all()
        owners = connection.execute(
            text("select owner, owner_address from marts.public_properties")
        ).all()

    assert [row.case_number for row in incidents] == ["26-1001", "26-1002"]
    assert all(
        row.officer is None and row.reference_number is None for row in incidents
    )
    # Title case, as the normalization job writes it.
    house, corner = incidents
    assert (house.location, house.lat, house.lng) == (
        "1200 block of Main St",
        43.642,
        -72.251,
    )
    assert corner.location == "Main St and Hanover St"
    assert (corner.lat, corner.lng) == (43.6431, -72.2501)
    assert owners == [(None, None)]


@pytest.mark.parametrize(
    ("ai_text", "public"),
    [
        ("Rear 12 Main St", "Main St"),
        ("Main St 12", "Main St"),
        ("12 Main St Lot 5", "Main St"),
        ("1234 Main St Apt 3 B", "1200 block of Main St"),
    ],
)
def test_the_ai_address_text_never_reaches_the_public_set(dbt, ai_text, public):
    """Only the matched street, at block level, is published, whatever the AI wrote."""
    rows = good_rows()
    rows[AddressNormalization][0]["normalized_address"] = ai_text
    dbt.seed_rows(rows)

    result = dbt.run("build")

    assert result.returncode == 0, result.output
    with dbt.engine.connect() as connection:
        location = connection.scalar(
            text(
                "select location from marts.public_incidents"
                " where case_number = '26-1001'"
            )
        )
    assert location == public


def test_a_location_waiting_for_review_has_no_public_location(dbt):
    """11.19: listed, but with no location and no pin, until it is reviewed."""
    rows = good_rows()
    rows[AddressNormalization][0]["needs_review"] = True
    dbt.seed_rows(rows)
    assert dbt.run("run").returncode == 0

    with dbt.engine.connect() as connection:
        incident = connection.execute(
            text(
                "select location, location_kind, lat, lng, coordinate_precision"
                " from marts.public_incidents where case_number = '26-1001'"
            )
        ).one()
        pins = (
            connection.execute(text("select raw_address from marts.public_addresses"))
            .scalars()
            .all()
        )

    assert tuple(incident) == (None, None, None, None, None)
    assert pins == ["Main St and Hanover St"]


def test_the_disposition_seed_is_the_parsers_list(dispositions_seed):
    sys.path.insert(0, str(PROJECT_DIR.parent / "scrapers"))
    from parsers.dispositions import _DISPOSITIONS

    lines = DISPOSITIONS_SEED.read_text().splitlines()

    assert lines == ["disposition", *sorted(_DISPOSITIONS)]


def test_the_city_bounds_match_the_geocoder():
    """14.2's coarse box and in_city_bounds must agree, corner for corner."""
    import yaml
    from locations.geocode import in_city_bounds

    project = yaml.safe_load((PROJECT_DIR / "dbt_project.yml").read_text())
    b = project["vars"]["city_bounds"]
    step = 0.001

    assert in_city_bounds(b["min_lat"], b["min_lng"])
    assert in_city_bounds(b["max_lat"], b["max_lng"])
    assert not in_city_bounds(b["min_lat"] - step, b["min_lng"])
    assert not in_city_bounds(b["max_lat"] + step, b["max_lng"])
    assert not in_city_bounds(b["min_lat"], b["min_lng"] - step)
    assert not in_city_bounds(b["max_lat"], b["max_lng"] + step)
