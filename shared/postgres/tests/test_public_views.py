"""The public views: what the static export may read, and what they hide."""

from datetime import date, datetime

import pytest
from postgres.models.address_normalization import AddressNormalization
from postgres.models.incident_type_category import IncidentTypeCategory
from postgres.models.log_entry import LogEntry
from sqlalchemy import text

NOW = datetime(2026, 11, 23)


def add_location(session, raw: str, **columns) -> None:
    values = {
        "normalized_address": raw.title(),
        "kind": "place",
        "street": "MAIN ST",
        "source": "ai",
        "lat": 43.64,
        "lng": -72.25,
        "coordinate_precision": "exact",
        **columns,
    }
    session.add(
        AddressNormalization(raw_address=raw, created_at=NOW, updated_at=NOW, **values)
    )
    session.flush()


def add_type(session, raw: str, normalized: str | None) -> None:
    session.add(
        IncidentTypeCategory(
            raw_incident_type=raw,
            normalized_type=normalized,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.flush()


def add_entry(session, number: int, **columns) -> None:
    values = {
        "source_url": "https://example.com/a.pdf",
        "log_date": date(2026, 6, 1),
        "incident_type": "Welfare Check",
        "location": "SHOP",
        **columns,
    }
    session.add(
        LogEntry(case_number=f"26-{number}", created_at=NOW, updated_at=NOW, **values)
    )
    session.flush()


def location(session, raw: str):
    return (
        session.execute(
            text("SELECT * FROM public_locations WHERE raw_address = :raw"),
            {"raw": raw},
        )
        .mappings()
        .one()
    )


def entry(session, number: int):
    return (
        session.execute(
            text("SELECT * FROM public_log_entries WHERE case_number = :case"),
            {"case": f"26-{number}"},
        )
        .mappings()
        .one()
    )


# --- public_locations ---


def test_an_unflagged_row_is_published_as_it_is(db_session):
    add_location(db_session, "SHOP")

    row = location(db_session, "SHOP")

    assert (row["normalized_address"], row["kind"], row["street"]) == (
        "Shop",
        "place",
        "MAIN ST",
    )
    assert (row["names_person"], row["lat"], row["lng"]) == (False, 43.64, -72.25)
    assert row["coordinate_precision"] == "exact"


def test_a_flagged_row_publishes_its_street_as_an_approximate_road_with_no_pin(
    db_session,
):
    add_location(db_session, "F AND CHILD", names_person=True)

    row = location(db_session, "F AND CHILD")

    assert (row["normalized_address"], row["kind"], row["street"]) == (
        "MAIN ST",
        "road",
        "MAIN ST",
    )
    assert (row["names_person"], row["lat"], row["lng"]) == (True, None, None)
    assert row["coordinate_precision"] == "approximate"


def test_a_row_that_becomes_human_after_the_migration_is_flagged(db_session):
    add_location(db_session, "SHOP")
    assert location(db_session, "SHOP")["names_person"] is False

    db_session.execute(
        text(
            "UPDATE address_normalizations SET source = 'human', lat = 43.7"
            " WHERE raw_address = 'SHOP'"
        )
    )

    row = location(db_session, "SHOP")
    assert (row["names_person"], row["normalized_address"], row["lat"]) == (
        True,
        "MAIN ST",
        None,
    )


def test_a_flagged_row_with_no_street_has_no_name_and_no_pin(db_session):
    add_location(db_session, "F AND CHILD", names_person=True, street=None)

    row = location(db_session, "F AND CHILD")

    assert (row["normalized_address"], row["lat"], row["lng"]) == (None, None, None)


def test_a_row_with_no_normalized_address_is_flagged_and_has_no_name(db_session):
    add_location(
        db_session,
        "UNKNOWN",
        normalized_address=None,
        kind=None,
        street=None,
        source=None,
        lat=None,
        lng=None,
        coordinate_precision=None,
    )

    row = location(db_session, "UNKNOWN")

    assert (row["names_person"], row["normalized_address"], row["kind"]) == (
        True,
        None,
        "road",
    )


def test_a_row_with_no_source_and_a_name_is_not_taken_for_human(db_session):
    add_location(db_session, "SHOP", source=None)

    assert location(db_session, "SHOP")["names_person"] is False


def test_the_view_has_one_row_per_normalization(db_session):
    add_location(db_session, "A")
    add_location(db_session, "B", names_person=True)

    count = db_session.execute(
        text("SELECT count(*) FROM public_locations")
    ).scalar_one()

    assert count == 2


# --- public_log_entries ---


def test_a_type_with_a_plain_name_reads_it_and_keeps_its_category(db_session):
    add_location(db_session, "SHOP")
    add_type(db_session, "73 YOM CPR", "Cardiac arrest")
    add_entry(db_session, 1, incident_type="73 YOM CPR")

    row = entry(db_session, 1)

    assert row["incident_type"] == "Cardiac arrest"
    assert row["raw_incident_type"] == "73 YOM CPR"
    assert row["category"] == "premises"


def test_a_type_with_no_plain_name_reads_other_and_keeps_its_category(db_session):
    add_type(db_session, "MV STOP - M-ARTHUR", None)
    add_entry(db_session, 1, incident_type="Motor Vehicle Stop - M-ARTHUR")
    add_entry(
        db_session, 2, incident_type="Some Unnamed Alarm", call_source="Alarm System"
    )

    traffic, alarm = entry(db_session, 1), entry(db_session, 2)

    assert (traffic["incident_type"], traffic["category"]) == ("Other", "traffic")
    assert (alarm["incident_type"], alarm["category"]) == ("Other", "alarms")
    assert traffic["raw_incident_type"] == "Motor Vehicle Stop - M-ARTHUR"


def test_an_entry_with_no_type_at_all_reads_other(db_session):
    add_entry(db_session, 1, incident_type=None)

    assert entry(db_session, 1)["incident_type"] == "Other"


def test_the_category_is_worked_out_from_the_logs_own_type(db_session):
    # The plain name has no traffic prefix, but the log's text does.
    add_type(db_session, "Motor Vehicle Stop - Warning", "Traffic warning")
    add_entry(db_session, 1, incident_type="Motor Vehicle Stop - Warning")

    row = entry(db_session, 1)

    assert (row["incident_type"], row["category"]) == ("Traffic warning", "traffic")


def test_an_entry_publishes_the_public_name_of_its_location(db_session):
    add_location(db_session, "SHOP")
    add_entry(db_session, 1)

    row = entry(db_session, 1)

    assert (row["location"], row["raw_location"]) == ("Shop", "SHOP")


def test_an_entry_at_a_flagged_location_publishes_its_street(db_session):
    add_location(db_session, "F AND CHILD", names_person=True)
    add_entry(db_session, 1, location="F AND CHILD")

    assert entry(db_session, 1)["location"] == "MAIN ST"


def test_an_entry_with_no_normalization_has_a_null_location(db_session):
    add_entry(db_session, 1, location="NEVER NORMALIZED")

    row = entry(db_session, 1)

    assert (row["location"], row["raw_location"]) == (None, "NEVER NORMALIZED")


def test_an_entry_with_no_location_has_a_null_location(db_session):
    add_entry(db_session, 1, location=None)

    assert entry(db_session, 1)["location"] is None


def test_one_log_row_is_one_view_row_whatever_it_joins(db_session):
    add_location(db_session, "SHOP")
    add_type(db_session, "Welfare Check", "Welfare check")
    add_entry(db_session, 1)
    add_entry(db_session, 2)

    count = db_session.execute(
        text("SELECT count(*) FROM public_log_entries")
    ).scalar_one()

    assert count == 2


@pytest.mark.parametrize(
    "column",
    [
        "officer_code",
        "place_code",
        "refer_to",
        "location_text",
    ],
)
def test_the_view_leaves_out_the_columns_the_export_does_not_read(db_session, column):
    columns = (
        db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_name = 'public_log_entries'"
            )
        )
        .scalars()
        .all()
    )

    assert column not in columns
