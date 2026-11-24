"""Holding unsafe person locations, on the real test database. Text here is made up."""

from datetime import date, datetime

import pytest
from postgres.models.address_normalization import AddressNormalization
from postgres.models.log_entry import LogEntry
from sqlalchemy import text

from scripts import privacy_holds
from scripts.privacy_holds import is_clearly_safe, is_plain_address

NOW = datetime(2026, 11, 24)
STREETS = {"placeholder lane"}


def add_location(session, raw: str, **columns) -> AddressNormalization:
    row = AddressNormalization(
        raw_address=raw, created_at=NOW, updated_at=NOW, **columns
    )
    session.add(row)
    session.commit()
    return row


# --- the safe rule ---


@pytest.mark.parametrize(
    ("normalized", "safe"),
    [
        ("12 Placeholder Lane", True),
        ("12A Placeholder Lane", True),
        ("Placeholder Lane", True),
        ("Zz Placeholder Person", False),
        ("Placeholder Lane Residence", False),
        ("Zz Business Place", False),
        (None, False),
    ],
)
def test_a_flagged_text_is_safe_only_as_a_plain_address_or_street(normalized, safe):
    assert is_clearly_safe(normalized, STREETS, set()) is safe


def test_a_flagged_text_that_an_unflagged_row_also_has_is_safe():
    assert is_clearly_safe("Zz Business Place", STREETS, {"zz business place"})


def test_a_plain_address_needs_a_street_from_the_list():
    assert is_plain_address("12 placeholder lane", STREETS)
    assert not is_plain_address("12 unknown road", STREETS)


# --- mark, list, handled ---


def test_mark_holds_only_the_flagged_rows_that_are_not_clearly_safe(db_session):
    street = "Placeholder Lane"
    add_location(
        db_session,
        "SAFE",
        normalized_address="12 Placeholder Lane",
        street=street,
        names_person=True,
    )
    unsafe = add_location(
        db_session, "UNSAFE", normalized_address="Zz Person Name", names_person=True
    )
    unflagged = add_location(
        db_session, "OTHER", normalized_address="Zz Unflagged Name", names_person=False
    )

    assert privacy_holds.mark(db_session) == (1, 1)

    db_session.refresh(unsafe)
    db_session.refresh(unflagged)
    assert unsafe.privacy_hold is True
    assert unflagged.privacy_hold is False


def test_mark_never_clears_a_hold(db_session):
    row = add_location(
        db_session,
        "KEPT",
        normalized_address="12 Placeholder Lane",
        street="Placeholder Lane",
        names_person=True,
        privacy_hold=True,
    )

    privacy_holds.mark(db_session)

    db_session.refresh(row)
    assert row.privacy_hold is True


def test_mark_twice_holds_once(db_session):
    add_location(
        db_session, "UNSAFE", normalized_address="Zz Person Name", names_person=True
    )
    assert privacy_holds.mark(db_session) == (1, 0)
    assert privacy_holds.mark(db_session) == (0, 0)


def test_waiting_lists_held_rows_that_are_not_handled(db_session):
    held = add_location(db_session, "HELD", names_person=True, privacy_hold=True)
    add_location(
        db_session, "DONE", names_person=True, privacy_hold=True, privacy_handled_at=NOW
    )
    add_location(db_session, "FREE", names_person=True)

    assert [row.id for row in privacy_holds.waiting(db_session)] == [held.id]


def test_handled_releases_a_held_row_once(db_session):
    held = add_location(db_session, "HELD", names_person=True, privacy_hold=True)

    assert privacy_holds.handle(db_session, [held.id]) == 1
    assert privacy_holds.handle(db_session, [held.id]) == 0

    db_session.refresh(held)
    assert held.privacy_handled_at is not None
    assert privacy_holds.waiting(db_session) == []


def test_handled_ignores_a_row_that_is_not_held(db_session):
    free = add_location(db_session, "FREE", names_person=True)
    assert privacy_holds.handle(db_session, [free.id]) == 0


def test_main_mark_prints_counts_and_never_the_text(db_session, capsys, monkeypatch):
    add_location(
        db_session,
        "ZZ SECRET RAW",
        normalized_address="Zz Secret Name",
        names_person=True,
    )
    monkeypatch.setattr(privacy_holds, "bootstrap", lambda name: None)
    monkeypatch.setattr(privacy_holds, "open_session", lambda: _Session(db_session))

    assert privacy_holds.main(["mark"]) == 0

    output = capsys.readouterr()
    assert "1 newly held" in output.out
    assert "SECRET" not in (output.out + output.err).upper()


class _Session:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *exc):
        return False


# --- what a hold does to the public data ---


def test_a_held_location_has_no_pin_or_place_card_and_its_entries_still_count(
    db_session,
):
    from pathlib import Path

    places_sql = (
        (Path(__file__).parents[2] / "tools/report-gen/src/sql/places.sql")
        .read_text()
        .replace("$1", ":since")
    )
    add_location(
        db_session,
        "HELD PLACE",
        normalized_address="Zz Held Name",
        kind="place",
        street="Placeholder Lane",
        names_person=True,
        privacy_hold=True,
        lat=43.6,
        lng=-72.2,
        coordinate_precision="exact",
        source="ai",
    )
    add_location(
        db_session,
        "SHOWN PLACE",
        normalized_address="12 Placeholder Lane",
        kind="place",
        street="Placeholder Lane",
        lat=43.7,
        lng=-72.3,
        coordinate_precision="exact",
        source="ai",
    )
    for number, location in enumerate(["HELD PLACE", "SHOWN PLACE"]):
        db_session.add(
            LogEntry(
                case_number=f"26-{number}",
                source_url="https://example.com/a.pdf",
                log_date=date(2026, 6, 1),
                incident_type="Welfare Check",
                location=location,
                created_at=NOW,
                updated_at=NOW,
            )
        )
    db_session.commit()

    pins = (
        db_session.execute(text(places_sql), {"since": date(2026, 1, 1)})
        .mappings()
        .all()
    )
    total = db_session.execute(
        text("SELECT COUNT(*) FROM public_log_entries WHERE parse_error = false")
    ).scalar_one()

    assert [pin["normalized_address"] for pin in pins] == ["12 Placeholder Lane"]
    assert "Zz Held Name" not in "".join(str(pin["card"]) for pin in pins)
    assert total == 2


# The shapes found on the dev data, with made-up text. The flagged row's raw text holds the
# name; its normalized text is what an unflagged twin also publishes.
@pytest.mark.parametrize(
    ("kind", "normalized"),
    [
        ("address", "Zzzzzzzzz Zz"),
        ("place", "Zzzzzzzzzzz Zzzzzzz"),
        ("place", "Zzzzzzzz Zzzz"),
        ("highway", "Z-99 Zzzzzzzzzz Zzzz Zzzz 99"),
    ],
)
def test_a_flagged_row_with_an_unflagged_twin_is_not_held(db_session, kind, normalized):
    flagged = add_location(
        db_session,
        "ZZ RAW NAME TEXT",
        normalized_address=normalized,
        kind=kind,
        names_person=True,
    )
    add_location(db_session, "ZZ TWIN RAW", normalized_address=normalized, kind=kind)

    assert privacy_holds.mark(db_session) == (0, 1)

    db_session.refresh(flagged)
    assert flagged.privacy_hold is False
