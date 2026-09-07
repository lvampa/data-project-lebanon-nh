from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db
from api.main import app


def _make_es_response(hits_per_index: dict[str, list[dict]]) -> dict:
    """Build a fake msearch response with the given hits per index name."""
    from api.routers.search import ES_INDICES

    responses = []
    for index in ES_INDICES:
        hits = hits_per_index.get(index, [])
        responses.append(
            {
                "hits": {
                    "hits": [
                        {
                            "_id": str(h["id"]),
                            "_score": h.get("score", 1.0),
                            "_source": h,
                        }
                        for h in hits
                    ]
                }
            }
        )
    return {"responses": responses}


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_es_singleton():
    import api.routers.search as search_mod

    search_mod._es = None
    yield
    search_mod._es = None


def test_search_returns_grouped_results():
    mock_db = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = (
        None  # no normalization
    )

    es_response = _make_es_response(
        {
            "properties": [
                {
                    "id": 1,
                    "entity_type": "properties",
                    "location": "304 HANOVER ST",
                    "owner": "SMITH",
                }
            ],
            "incidents": [
                {
                    "id": 10,
                    "entity_type": "incidents",
                    "location": "304 HANOVER ST",
                    "incident_type": "Theft",
                }
            ],
        }
    )

    with patch("api.routers.search.Elasticsearch") as MockES:
        es_instance = MagicMock()
        MockES.return_value = es_instance
        es_instance.msearch.return_value = es_response
        app.dependency_overrides[get_db] = lambda: mock_db
        client = TestClient(app)
        resp = client.get("/api/search?q=304+Hanover+St")

    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "304 Hanover St"
    assert len(data["results"]["properties"]) == 1
    assert len(data["results"]["incidents"]) == 1
    assert data["results"]["properties"][0]["id"] == 1


def test_search_returns_empty_when_no_hits():
    mock_db = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    es_response = _make_es_response({})

    with patch("api.routers.search.Elasticsearch") as MockES:
        es_instance = MagicMock()
        MockES.return_value = es_instance
        es_instance.msearch.return_value = es_response
        app.dependency_overrides[get_db] = lambda: mock_db
        client = TestClient(app)
        resp = client.get("/api/search?q=nothing")

    assert resp.status_code == 200
    data = resp.json()
    for index_results in data["results"].values():
        assert index_results == []


def test_search_uses_normalized_query_when_address_match():
    from postgres.models.address_normalization import AddressNormalization

    mock_db = MagicMock()
    norm_row = MagicMock(spec=AddressNormalization)
    norm_row.normalized_address = "304 hanover st lebanon nh"
    mock_db.execute.return_value.scalar_one_or_none.return_value = norm_row

    es_response = _make_es_response({})

    with patch("api.routers.search.Elasticsearch") as MockES:
        es_instance = MagicMock()
        MockES.return_value = es_instance
        es_instance.msearch.return_value = es_response
        app.dependency_overrides[get_db] = lambda: mock_db
        client = TestClient(app)
        resp = client.get("/api/search?q=304+Hanover+St")

    assert resp.status_code == 200
    data = resp.json()
    assert data["normalized_query"] == "304 hanover st lebanon nh"


def test_search_normalized_query_is_none_when_no_match():
    mock_db = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    es_response = _make_es_response({})

    with patch("api.routers.search.Elasticsearch") as MockES:
        es_instance = MagicMock()
        MockES.return_value = es_instance
        es_instance.msearch.return_value = es_response
        app.dependency_overrides[get_db] = lambda: mock_db
        client = TestClient(app)
        resp = client.get("/api/search?q=unknown place")

    assert resp.status_code == 200
    assert resp.json()["normalized_query"] is None


def test_search_requires_q_param():
    client = TestClient(app)
    resp = client.get("/api/search")
    assert resp.status_code == 422
