from datetime import UTC, datetime

from postgres.models.llc import Llc as LlcModel


def _make_llc(**kwargs) -> LlcModel:
    defaults = {
        "id": 1,
        "name": "TIMBERWOOD PROPERTIES LLC",
        "raw_owner_name": "Timberwood Properties LLC",
        "lookup_status": "pending",
        "nh_business_id": None,
        "business_status": None,
        "formation_date": None,
        "business_email": None,
        "phone": None,
        "registered_agent": None,
        "registered_agent_address": None,
        "principals": None,
        "last_looked_up_at": None,
        "error_message": None,
        "created_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return LlcModel(**defaults)


def test_list_llcs_empty(mock_db, client):
    mock_db.scalar.return_value = 0
    mock_db.scalars.return_value.all.return_value = []

    resp = client.get("/api/llcs")

    assert resp.status_code == 200
    data = resp.json()
    assert data == {"total": 0, "items": []}


def test_list_llcs_returns_llc(mock_db, client):
    llc = _make_llc()
    mock_db.scalar.return_value = 1
    mock_db.scalars.return_value.all.return_value = [llc]

    resp = client.get("/api/llcs")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "TIMBERWOOD PROPERTIES LLC"
    assert data["items"][0]["lookup_status"] == "pending"


def test_list_llcs_filters_by_lookup_status(mock_db, client):
    mock_db.scalar.return_value = 0
    mock_db.scalars.return_value.all.return_value = []

    resp = client.get("/api/llcs?lookup_status=pending")

    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_list_llcs_rejects_unknown_lookup_status(mock_db, client):
    resp = client.get("/api/llcs?lookup_status=bogus")

    assert resp.status_code == 422
    mock_db.scalars.assert_not_called()


def test_patch_llc_status_updates_correctly(mock_db, client):
    llc = _make_llc(lookup_status="pending")
    mock_db.get.return_value = llc

    resp = client.patch("/api/llcs/1/status", json={"lookup_status": "complete"})

    assert resp.status_code == 200
    assert llc.lookup_status == "complete"
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(llc)


def test_patch_llc_status_invalid_returns_422(mock_db, client):

    resp = client.patch("/api/llcs/1/status", json={"lookup_status": "bad_status"})

    assert resp.status_code == 422


def test_patch_llc_status_not_found_returns_404(mock_db, client):
    mock_db.get.return_value = None

    resp = client.patch("/api/llcs/999/status", json={"lookup_status": "complete"})

    assert resp.status_code == 404
