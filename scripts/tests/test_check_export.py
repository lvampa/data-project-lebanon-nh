"""The export checks, on small folders and the real test database."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from postgres.models.address_normalization import AddressNormalization

from scripts.check_export import (
    check_coverage,
    check_files,
    check_person_text,
    check_prompt_versions,
)
from scripts.normalize.prompts import (
    LOCATION_PROMPT_VERSION,
    MIN_PRIVACY_LOCATION_PROMPT,
)

NOW = datetime(2026, 11, 24)
PLACE = "ZZ Placeholder Person Lane 99"


def write(export: Path, name: str, data: object) -> None:
    path = export / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


@pytest.fixture
def export(tmp_path: Path) -> Path:
    for name in (
        "incidents.json",
        "activity.json",
        "staff.json",
        "properties.json",
    ):
        write(tmp_path, name, [])
    write(tmp_path, "stats.json", {"total": 100, "mapped_total": 90})
    write(tmp_path, "addresses.json", [{"id": "main-st"}])
    write(tmp_path, "places/main-st.json", {})
    return tmp_path


def add_location(session, raw: str, **columns) -> None:
    session.add(
        AddressNormalization(raw_address=raw, created_at=NOW, updated_at=NOW, **columns)
    )
    session.commit()


def test_a_complete_export_passes_the_file_checks(export):
    assert check_files(export) == []
    assert check_coverage(export) == []


def test_a_missing_file_is_named(export):
    (export / "staff.json").unlink()
    assert check_files(export) == ["staff.json is missing"]


def test_a_pin_without_a_card_is_counted(export):
    write(export, "addresses.json", [{"id": "main-st"}, {"id": "gone"}])
    assert check_files(export) == ["1 places have no card file"]


def test_coverage_below_the_floor_fails(export):
    write(export, "stats.json", {"total": 100, "mapped_total": 84})
    assert "below 85%" in check_coverage(export)[0]


def test_an_export_with_no_entries_fails(export):
    write(export, "stats.json", {"total": 0, "mapped_total": 0})
    assert check_coverage(export) == ["stats.json counts no entries"]


def test_a_flagged_person_location_in_the_export_fails_without_printing_it(
    export, db_session
):
    add_location(db_session, PLACE.upper(), normalized_address=PLACE, names_person=True)
    write(export, "incidents.json", [{"location": PLACE.lower()}])

    problems = check_person_text(export, db_session)

    assert problems == ["1 flagged person locations appear in the export"]
    assert PLACE not in " ".join(problems)


def test_a_normalized_text_that_an_unflagged_location_also_produces_is_not_a_leak(
    export, db_session
):
    add_location(db_session, "RAW ONE", normalized_address=PLACE, names_person=True)
    add_location(db_session, "RAW TWO", normalized_address=PLACE, names_person=False)
    write(export, "incidents.json", [{"location": PLACE}])
    assert check_person_text(export, db_session) == []


def test_a_flagged_rows_raw_text_in_the_export_fails_even_with_an_unflagged_twin(
    export, db_session
):
    raw = "ZZ RAW PERSON TEXT 7"
    add_location(db_session, raw, normalized_address=PLACE, names_person=True)
    add_location(db_session, "OTHER", normalized_address=PLACE, names_person=False)
    write(export, "incidents.json", [{"location": raw}])
    assert check_person_text(export, db_session) == [
        "1 flagged person locations appear in the export"
    ]


def test_a_held_rows_text_in_the_export_still_fails(export, db_session):
    add_location(
        db_session,
        PLACE,
        normalized_address=PLACE,
        names_person=True,
        privacy_hold=True,
    )
    write(export, "incidents.json", [{"location": PLACE}])
    assert check_person_text(export, db_session) == [
        "1 flagged person locations appear in the export"
    ]


def test_a_parcel_address_equal_to_a_flagged_location_is_not_a_leak(export, db_session):
    add_location(db_session, PLACE, normalized_address=PLACE, names_person=True)
    write(export, "properties.json", [{"location": PLACE}])
    assert check_person_text(export, db_session) == []


def test_a_flagged_location_that_is_not_in_the_export_passes(export, db_session):
    add_location(db_session, PLACE, normalized_address=PLACE, names_person=True)
    assert check_person_text(export, db_session) == []


def test_the_street_of_a_flagged_location_may_appear(export, db_session):
    add_location(
        db_session,
        "Person Lane 99",
        normalized_address="Person Lane 99",
        street="Person Lane 99",
        names_person=True,
    )
    write(export, "incidents.json", [{"location": "Person Lane 99"}])
    assert check_person_text(export, db_session) == []


def test_a_short_flagged_text_is_not_scanned(export, db_session):
    add_location(db_session, "Elm St", normalized_address="Elm St", names_person=True)
    write(export, "incidents.json", [{"location": "Elm St"}])
    assert check_person_text(export, db_session) == []


@pytest.mark.parametrize(
    "version", ["location-1", "location-1+streets-abc", None, "odd"]
)
def test_an_ai_location_without_the_person_flag_fails(db_session, version):
    add_location(
        db_session,
        "a",
        normalized_address="1 A St",
        source="ai",
        prompt_version=version,
    )
    assert check_prompt_versions(db_session) == [
        "1 AI locations are on a prompt without the person flag"
    ]


def test_an_ai_location_on_the_first_flagged_prompt_passes(db_session):
    add_location(
        db_session,
        "a",
        normalized_address="1 A St",
        source="ai",
        prompt_version=f"location-{MIN_PRIVACY_LOCATION_PROMPT}+streets-abc",
    )
    assert check_prompt_versions(db_session) == []


def test_the_privacy_minimum_is_not_newer_than_the_current_prompt():
    assert int(LOCATION_PROMPT_VERSION.split("-")[1]) >= MIN_PRIVACY_LOCATION_PROMPT


def test_current_ai_and_rule_locations_pass(db_session):
    add_location(
        db_session,
        "a",
        normalized_address="1 A St",
        source="ai",
        prompt_version=f"{LOCATION_PROMPT_VERSION}+streets-abc",
    )
    add_location(
        db_session,
        "b",
        normalized_address="2 B St",
        source="rule",
        prompt_version="rules-3",
    )
    assert check_prompt_versions(db_session) == []
