"""The admin API for both normalized fields, against the real test database."""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from postgres.models.address_normalization import AddressNormalization
from postgres.models.incident_type_category import IncidentTypeCategory
from postgres.models.log_entry import LogEntry
from sqlalchemy import select

from api.main import app
from api.schemas import CATEGORIES
from api.tests.conftest import ADMIN_TOKEN
from scripts.models import INCIDENT_CATEGORIES

NOW = datetime(2026, 11, 13)


@pytest.fixture
def real_client(db_connection):
    """No mocked session: SessionLocal is bound to the test's rolled-back connection."""
    with TestClient(app, headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}) as client:
        yield client


def add_entry(session, case_number: str, **columns) -> None:
    session.add(
        LogEntry(
            case_number=case_number,
            source_url="https://example.com/log.pdf",
            log_date=date(2026, 5, 11),
            created_at=NOW,
            updated_at=NOW,
            **columns,
        )
    )
    session.commit()


def add_category(session, raw: str, **columns) -> None:
    session.add(
        IncidentTypeCategory(
            raw_incident_type=raw, created_at=NOW, updated_at=NOW, **columns
        )
    )
    session.commit()


def add_address(session, raw: str, **columns) -> None:
    session.add(
        AddressNormalization(raw_address=raw, created_at=NOW, updated_at=NOW, **columns)
    )
    session.commit()


def category_row(session, raw: str) -> IncidentTypeCategory | None:
    session.expire_all()
    return session.scalar(
        select(IncidentTypeCategory).where(
            IncidentTypeCategory.raw_incident_type == raw
        )
    )


def the_category(session, raw: str) -> IncidentTypeCategory:
    row = category_row(session, raw)
    assert row is not None, f"no category row for {raw!r}"
    return row


def the_address(session, raw: str) -> AddressNormalization:
    row = address_row(session, raw)
    assert row is not None, f"no address row for {raw!r}"
    return row


def address_row(session, raw: str) -> AddressNormalization | None:
    session.expire_all()
    return session.scalar(
        select(AddressNormalization).where(AddressNormalization.raw_address == raw)
    )


def raws(response, key: str) -> list[str]:
    return [item[key] for item in response.json()["items"]]


def test_the_api_and_the_scripts_agree_on_the_five_categories():
    assert tuple(CATEGORIES) == INCIDENT_CATEGORIES


# --- the categories list (7.3, 7.4) ---


def test_the_list_shows_source_review_mark_normalized_type_and_entry_count(
    db_session, real_client
):
    add_entry(db_session, "26-1", incident_type="MV STOP")
    add_entry(db_session, "26-2", incident_type="MV STOP")
    add_category(
        db_session,
        "MV STOP",
        category="Traffic",
        normalized_type="Traffic stop",
        source="ai",
        needs_review=True,
    )

    response = real_client.get("/api/categories")

    [item] = response.json()["items"]
    assert item["raw_incident_type"] == "MV STOP"
    assert item["count"] == 2
    assert item["category"] == "Traffic"
    assert item["normalized_type"] == "Traffic stop"
    assert item["source"] == "ai"
    assert item["needs_review"] is True
    assert item["is_categorized"] is True


def test_the_list_keeps_a_subcategory_field_that_mirrors_normalized_type(
    db_session, real_client
):
    add_entry(db_session, "26-1", incident_type="MV STOP")
    add_category(
        db_session, "MV STOP", category="Traffic", normalized_type="Traffic stop"
    )

    [item] = real_client.get("/api/categories").json()["items"]

    assert item["subcategory"] == "Traffic stop"


def test_a_raw_value_with_no_normalization_still_appears_with_empty_fields(
    db_session, real_client
):
    add_entry(db_session, "26-1", incident_type="NOISE")

    [item] = real_client.get("/api/categories").json()["items"]

    assert (item["category"], item["source"], item["needs_review"]) == (
        None,
        None,
        False,
    )
    assert item["is_categorized"] is False


def test_the_list_filters_by_source(db_session, real_client):
    for case, raw, source in [("1", "A", "ai"), ("2", "B", "human"), ("3", "C", None)]:
        add_entry(db_session, case, incident_type=raw)
        add_category(db_session, raw, category="Police", source=source)

    assert raws(
        real_client.get("/api/categories?source=human"), "raw_incident_type"
    ) == ["B"]
    assert raws(real_client.get("/api/categories?source=ai"), "raw_incident_type") == [
        "A"
    ]


def test_the_list_filters_by_review_mark(db_session, real_client):
    add_entry(db_session, "1", incident_type="A")
    add_entry(db_session, "2", incident_type="B")
    add_category(db_session, "A", category="Police", needs_review=True)

    marked = real_client.get("/api/categories?needs_review=true")
    unmarked = real_client.get("/api/categories?needs_review=false")

    assert raws(marked, "raw_incident_type") == ["A"]
    assert raws(unmarked, "raw_incident_type") == ["B"]


def test_the_list_filters_by_whether_a_normalization_exists(db_session, real_client):
    add_entry(db_session, "1", incident_type="HAS")
    add_entry(db_session, "2", incident_type="WAITS")
    add_entry(db_session, "3", incident_type="NO ROW")
    add_category(db_session, "HAS", category="Fire")
    add_category(db_session, "WAITS")  # a row with no value: failed attempts live here

    done = real_client.get("/api/categories?normalized=true")
    waiting = real_client.get("/api/categories?normalized=false")

    assert raws(done, "raw_incident_type") == ["HAS"]
    assert sorted(raws(waiting, "raw_incident_type")) == ["NO ROW", "WAITS"]


def test_an_unknown_source_filter_is_a_422(real_client):
    assert real_client.get("/api/categories?source=robot").status_code == 422


# --- saving a category (7.5, 7.6, 7.7) ---


def test_a_patch_sets_the_source_to_human_and_clears_the_review_mark(
    db_session, real_client
):
    add_category(
        db_session,
        "MV STOP",
        category="Police",
        normalized_type="Stop",
        source="ai",
        prompt_version="incident_type-1",
        ai_call_id="abc123",
        needs_review=True,
    )

    response = real_client.patch(
        "/api/categories/MV STOP",
        json={"category": "Traffic", "normalized_type": "Traffic stop"},
    )

    assert response.status_code == 200
    row = the_category(db_session, "MV STOP")
    assert (row.category, row.normalized_type) == ("Traffic", "Traffic stop")
    assert (row.source, row.needs_review) == ("human", False)
    # A human value has no prompt version, and the AI call that came before it stays.
    assert (row.prompt_version, row.ai_call_id) == (None, "abc123")


def test_a_patch_can_set_a_value_that_has_no_normalization_yet(db_session, real_client):
    add_entry(db_session, "1", incident_type="NOISE")

    real_client.patch("/api/categories/NOISE", json={"category": "Police"})

    row = the_category(db_session, "NOISE")
    assert (row.category, row.source) == ("Police", "human")


@pytest.mark.parametrize("category", ["Parking", "", "police"])
def test_a_category_outside_the_five_is_rejected_with_422_and_nothing_is_saved(
    db_session, real_client, category
):
    response = real_client.patch("/api/categories/NOISE", json={"category": category})

    assert response.status_code == 422
    assert category_row(db_session, "NOISE") is None


def test_a_raw_value_with_a_slash_and_an_apostrophe_can_be_saved_and_deleted(
    db_session, real_client
):
    raw = "911 Hang-Ups/Abandoned Calls (Don't Call)"
    add_entry(db_session, "1", incident_type=raw)

    saved = real_client.patch(f"/api/categories/{raw}", json={"category": "Police"})
    listed = real_client.get("/api/categories")

    assert saved.status_code == 200
    assert saved.json()["raw_incident_type"] == raw
    assert raws(listed, "raw_incident_type") == [raw]
    assert real_client.delete(f"/api/categories/{raw}").status_code == 204
    assert category_row(db_session, raw) is None


# --- handing a value back to AI (7.12) ---


def test_a_delete_removes_the_row_and_its_failed_attempts(db_session, real_client):
    add_entry(db_session, "1", incident_type="NOISE")
    add_category(
        db_session, "NOISE", category="Police", source="human", failed_attempts=2
    )

    response = real_client.delete("/api/categories/NOISE")

    assert response.status_code == 204
    assert category_row(db_session, "NOISE") is None
    [item] = real_client.get("/api/categories").json()["items"]
    assert (item["category"], item["source"]) == (None, None)


def test_deleting_a_value_with_no_row_is_a_404(real_client):
    assert real_client.delete("/api/categories/NOTHING").status_code == 404


# --- the same for addresses ---


def test_the_address_list_shows_kind_source_review_mark_and_count(
    db_session, real_client
):
    add_entry(db_session, "1", location="12 MAIN ST")
    add_entry(db_session, "2", location="12 MAIN ST")
    add_address(
        db_session,
        "12 MAIN ST",
        normalized_address="12 Main St",
        kind="address",
        source="rule",
        needs_review=True,
        lat=43.64,
        lng=-72.25,
    )

    [item] = real_client.get("/api/addresses").json()["items"]

    assert item["count"] == 2
    assert (item["kind"], item["source"], item["needs_review"]) == (
        "address",
        "rule",
        True,
    )
    assert item["is_normalized"] is True


def test_the_address_list_filters_by_source_review_mark_and_existence(
    db_session, real_client
):
    for case, raw, columns in [
        ("1", "A", {"normalized_address": "A", "source": "ai"}),
        (
            "2",
            "B",
            {"normalized_address": "B", "source": "human", "needs_review": True},
        ),
        ("3", "C", {}),
    ]:
        add_entry(db_session, case, location=raw)
        if columns:
            add_address(db_session, raw, **columns)

    assert raws(real_client.get("/api/addresses?source=human"), "raw_address") == ["B"]
    assert raws(real_client.get("/api/addresses?needs_review=true"), "raw_address") == [
        "B"
    ]
    assert raws(real_client.get("/api/addresses?normalized=false"), "raw_address") == [
        "C"
    ]


def test_an_address_patch_sets_human_clears_the_mark_and_keeps_manual_coordinates(
    db_session, real_client
):
    add_address(db_session, "12 MAIN ST", source="ai", needs_review=True, kind="place")

    response = real_client.patch(
        "/api/addresses/12 MAIN ST",
        json={
            "normalized_address": "12 Main St",
            "kind": "address",
            # Outside the city bounds on purpose: a call the police answered next door.
            "lat": 43.70,
            "lng": -72.10,
            "geocode": False,
        },
    )

    assert response.status_code == 200
    row = the_address(db_session, "12 MAIN ST")
    assert (row.source, row.needs_review, row.kind) == ("human", False, "address")
    assert (row.lat, row.lng, row.geocoded_via) == (43.70, -72.10, "manual")


def test_an_address_kind_outside_the_four_is_a_422(db_session, real_client):
    response = real_client.patch(
        "/api/addresses/12 MAIN ST",
        json={"normalized_address": "12 Main St", "kind": "landmark", "geocode": False},
    )

    assert response.status_code == 422
    assert address_row(db_session, "12 MAIN ST") is None


def test_an_address_with_a_slash_and_an_apostrophe_round_trips(db_session, real_client):
    raw = "HANNAFORD'S - MAIN ST/ELM ST"
    add_entry(db_session, "1", location=raw)

    saved = real_client.patch(
        f"/api/addresses/{raw}",
        json={"normalized_address": "Main St and Elm St", "geocode": False},
    )

    assert saved.status_code == 200
    assert raws(real_client.get("/api/addresses"), "raw_address") == [raw]
    assert real_client.delete(f"/api/addresses/{raw}").status_code == 204
    assert address_row(db_session, raw) is None


def test_an_address_delete_hands_the_value_back(db_session, real_client):
    add_address(db_session, "12 MAIN ST", source="human", failed_attempts=1)

    assert real_client.delete("/api/addresses/12 MAIN ST").status_code == 204
    assert address_row(db_session, "12 MAIN ST") is None
    assert real_client.delete("/api/addresses/12 MAIN ST").status_code == 404


def test_patch_and_delete_need_the_admin_token(db_connection):
    anonymous = TestClient(app)

    assert (
        anonymous.patch("/api/categories/X", json={"category": "Fire"}).status_code
        == 401
    )
    assert anonymous.delete("/api/categories/X").status_code == 401
    assert anonymous.delete("/api/addresses/X").status_code == 401
