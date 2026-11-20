import csv
from datetime import date, datetime

import pytest
from postgres.models.address_normalization import AddressNormalization
from postgres.models.log_entry import LogEntry
from sqlalchemy import select

from scripts.normalize import place_sheet

NOW = datetime(2026, 11, 20)
STREET_POINT = (43.6740, -72.2656)


def add_place(
    session, raw: str, normalized: str, calls: tuple[str, ...] = ("Alarm",), **columns
) -> None:
    values = {
        "kind": "place",
        "source": "ai",
        "street": "MOUNT SUPPORT RD",
        "lat": STREET_POINT[0],
        "lng": STREET_POINT[1],
        "coordinate_precision": "approximate",
        "geocoded_via": "nominatim",
        **columns,
    }
    session.add(
        AddressNormalization(
            raw_address=raw,
            normalized_address=normalized,
            created_at=NOW,
            updated_at=NOW,
            **values,
        )
    )
    for number, incident_type in enumerate(calls):
        session.add(
            LogEntry(
                case_number=f"{raw}-{number}",
                source_url="https://example.com/a.pdf",
                log_date=date(2026, 6, 1),
                location=raw,
                incident_type=incident_type,
                created_at=NOW,
                updated_at=NOW,
            )
        )
    session.commit()


def read(path) -> list[dict[str, str]]:
    with path.open() as handle:
        return list(csv.DictReader(handle))


def fill(path, **typed: tuple[str, str]) -> None:
    """Fill lat and lng for the rows named by their `name` column."""
    rows = read(path)
    for row in rows:
        if row["name"] in typed:
            row["lat"], row["lng"] = typed[row["name"]]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=place_sheet.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def row_for(session, raw: str) -> AddressNormalization:
    session.expire_all()
    return session.scalars(
        select(AddressNormalization).where(AddressNormalization.raw_address == raw)
    ).one()


# --- export ---


def test_the_sheet_lists_approximate_places_busiest_first(db_session, tmp_path):
    add_place(db_session, "QUIET", "Quiet Shop, Mount Support Rd")
    add_place(
        db_session, "BUSY", "Busy Shop, Mount Support Rd", ("Alarm", "Welfare Check")
    )
    path = tmp_path / "sheet.csv"

    count = place_sheet.export_sheet(db_session, path)

    rows = read(path)
    assert count == 2
    assert [(r["name"], r["calls"]) for r in rows] == [
        ("Busy Shop", "2"),
        ("Quiet Shop", "1"),
    ]
    first = rows[0]
    assert first["street"] == "MOUNT SUPPORT RD"
    assert (first["current_lat"], first["current_lng"]) == ("43.674", "-72.2656")
    assert "mlat=43.674&mlon=-72.2656" in first["openstreetmap"]
    assert (first["lat"], first["lng"]) == ("", "")


def test_calls_count_everything_but_road_traffic(db_session, tmp_path):
    add_place(
        db_session,
        "SHOP",
        "Shop, Mount Support Rd",
        ("Alarm", "Motor Vehicle Stop", "MV Complaint", "Welfare Check"),
    )

    place_sheet.export_sheet(db_session, tmp_path / "sheet.csv")

    assert read(tmp_path / "sheet.csv")[0]["calls"] == "2"


def test_a_place_with_only_traffic_calls_is_not_listed(db_session, tmp_path):
    add_place(db_session, "SHOP", "Shop, Mount Support Rd", ("Motor Vehicle Stop",))

    assert place_sheet.export_sheet(db_session, tmp_path / "sheet.csv") == 0


def test_calls_before_since_are_not_counted(db_session, tmp_path):
    add_place(db_session, "SHOP", "Shop, Mount Support Rd")

    count = place_sheet.export_sheet(
        db_session, tmp_path / "sheet.csv", date(2026, 7, 1)
    )

    assert count == 0


@pytest.mark.parametrize(
    "columns",
    [
        {"kind": "intersection", "normalized_address": "A St and B St"},
        {"source": "human"},
        {"coordinate_precision": "exact"},
    ],
    ids=["intersection", "human", "exact"],
)
def test_other_rows_are_not_listed(db_session, tmp_path, columns):
    normalized = columns.pop("normalized_address", "Shop, Mount Support Rd")
    add_place(db_session, "ROW", normalized, **columns)

    assert place_sheet.export_sheet(db_session, tmp_path / "sheet.csv") == 0


def test_a_bare_street_is_a_road_and_is_not_listed_but_a_house_address_is(
    db_session, tmp_path
):
    add_place(db_session, "ROAD", "Mount Support Rd")
    add_place(db_session, "HOUSE", "8 Commerce Ave", kind="address")

    place_sheet.export_sheet(db_session, tmp_path / "sheet.csv")

    assert [r["name"] for r in read(tmp_path / "sheet.csv")] == ["8 Commerce Ave"]


def test_text_that_could_run_as_a_formula_is_quoted_in_the_sheet(db_session, tmp_path):
    add_place(db_session, "ODD", "=CMD(), Mount Support Rd")

    place_sheet.export_sheet(db_session, tmp_path / "sheet.csv")

    [row] = read(tmp_path / "sheet.csv")
    assert row["name"] == "'=CMD()"
    assert row["current_lng"] == "-72.2656"


# --- import ---


def test_a_filled_row_sets_every_row_for_the_address_as_a_human_placement(
    db_session, tmp_path
):
    add_place(db_session, "SHOP A", "Shop, Mount Support Rd")
    add_place(db_session, "SHOP B", "Shop, Mount Support Rd")
    path = tmp_path / "sheet.csv"
    place_sheet.export_sheet(db_session, path)
    fill(path, Shop=("43.6700", "-72.2600"))

    result = place_sheet.import_sheet(db_session, path)

    assert (result.changed_places, result.changed_rows, result.rejected) == (1, 2, [])
    for raw in ("SHOP A", "SHOP B"):
        row = row_for(db_session, raw)
        assert (row.lat, row.lng) == (43.67, -72.26)
        assert (row.source, row.geocoded_via, row.coordinate_precision) == (
            "human",
            "manual",
            "exact",
        )
        assert (row.needs_review, row.osm_ref) == (False, None)


def test_blank_rows_are_skipped_and_counted(db_session, tmp_path):
    add_place(db_session, "SHOP", "Shop, Mount Support Rd")
    path = tmp_path / "sheet.csv"
    place_sheet.export_sheet(db_session, path)

    result = place_sheet.import_sheet(db_session, path)

    assert (result.blank, result.changed_places) == (1, 0)
    assert row_for(db_session, "SHOP").source == "ai"


@pytest.mark.parametrize(
    ("lat", "lng", "why"),
    [
        ("43.67", "", "both be numbers"),
        ("north", "-72.26", "both be numbers"),
        ("43.2081", "-71.5376", "outside Lebanon"),
        ("0", "0", "outside Lebanon"),
    ],
)
def test_a_bad_row_is_rejected_with_its_line_and_changes_nothing(
    db_session, tmp_path, lat, lng, why
):
    add_place(db_session, "SHOP", "Shop, Mount Support Rd")
    path = tmp_path / "sheet.csv"
    place_sheet.export_sheet(db_session, path)
    fill(path, Shop=(lat, lng))

    result = place_sheet.import_sheet(db_session, path)

    [(line, reason)] = result.rejected
    assert line == 2 and why in reason
    row = row_for(db_session, "SHOP")
    assert (row.lat, row.source) == (STREET_POINT[0], "ai")


def test_a_human_row_is_never_overwritten(db_session, tmp_path):
    add_place(db_session, "SHOP", "Shop, Mount Support Rd")
    path = tmp_path / "sheet.csv"
    place_sheet.export_sheet(db_session, path)
    fill(path, Shop=("43.6700", "-72.2600"))
    add_place(
        db_session,
        "SHOP HUMAN",
        "Shop, Mount Support Rd",
        source="human",
        lat=STREET_POINT[0],
        lng=STREET_POINT[1],
    )

    place_sheet.import_sheet(db_session, path)

    human = row_for(db_session, "SHOP HUMAN")
    assert (human.lat, human.source) == (STREET_POINT[0], "human")


def test_a_row_the_geocode_job_moved_since_the_export_is_left_alone(
    db_session, tmp_path
):
    add_place(db_session, "SHOP", "Shop, Mount Support Rd")
    path = tmp_path / "sheet.csv"
    place_sheet.export_sheet(db_session, path)
    fill(path, Shop=("43.6700", "-72.2600"))
    moved = row_for(db_session, "SHOP")
    moved.lat, moved.coordinate_precision = 43.65, "exact"
    db_session.commit()

    result = place_sheet.import_sheet(db_session, path)

    assert result.changed_rows == 0
    assert "nothing was changed" in result.rejected[0][1]
    assert row_for(db_session, "SHOP").lat == 43.65


def test_a_quoted_address_still_matches_after_the_round_trip(db_session, tmp_path):
    add_place(db_session, "ODD", "=CMD(), Mount Support Rd")
    path = tmp_path / "sheet.csv"
    place_sheet.export_sheet(db_session, path)
    fill(path, **{"'=CMD()": ("43.6700", "-72.2600")})

    result = place_sheet.import_sheet(db_session, path)

    assert result.changed_places == 1


# --- the command ---


def test_main_exports_then_imports_and_reports(db_session, tmp_path, capsys):
    add_place(db_session, "SHOP", "Shop, Mount Support Rd")
    path = tmp_path / "sheet.csv"

    assert place_sheet.main(["export", str(path)]) == 0
    fill(path, Shop=("43.6700", "-72.2600"))
    assert place_sheet.main(["import", str(path)]) == 0

    out = capsys.readouterr().out
    assert "Wrote 1 places" in out
    assert "1 places set by hand (1 rows), 0 blank rows skipped, 0 rejected." in out


def test_main_import_returns_1_when_a_row_is_rejected(db_session, tmp_path, capsys):
    add_place(db_session, "SHOP", "Shop, Mount Support Rd")
    path = tmp_path / "sheet.csv"
    place_sheet.main(["export", str(path)])
    fill(path, Shop=("0", "0"))

    assert place_sheet.main(["import", str(path)]) == 1
    assert "line 2" in capsys.readouterr().out
