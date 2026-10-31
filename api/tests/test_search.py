from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db
from api.main import ES_HOST, app
from api.routers.search import get_es


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
def mock_es():
    es = MagicMock()
    app.dependency_overrides[get_es] = lambda: es
    return es


def test_search_returns_grouped_results(mock_es):
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

    mock_es.msearch.return_value = es_response
    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app)
    resp = client.get("/api/search?q=304+Hanover+St")

    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "304 Hanover St"
    assert len(data["results"]["properties"]) == 1
    assert len(data["results"]["incidents"]) == 1
    assert data["results"]["properties"][0]["id"] == 1


def test_search_returns_empty_when_no_hits(mock_es):
    mock_db = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    es_response = _make_es_response({})

    mock_es.msearch.return_value = es_response
    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app)
    resp = client.get("/api/search?q=nothing")

    assert resp.status_code == 200
    data = resp.json()
    for index_results in data["results"].values():
        assert index_results == []


def test_search_uses_normalized_query_when_address_match(mock_es):
    from postgres.models.address_normalization import AddressNormalization

    mock_db = MagicMock()
    norm_row = MagicMock(spec=AddressNormalization)
    norm_row.normalized_address = "304 hanover st lebanon nh"
    mock_db.execute.return_value.scalar_one_or_none.return_value = norm_row

    es_response = _make_es_response({})

    mock_es.msearch.return_value = es_response
    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app)
    resp = client.get("/api/search?q=304+Hanover+St")

    assert resp.status_code == 200
    data = resp.json()
    assert data["normalized_query"] == "304 hanover st lebanon nh"


def test_search_normalized_query_is_none_when_no_match(mock_es):
    mock_db = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    es_response = _make_es_response({})

    mock_es.msearch.return_value = es_response
    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app)
    resp = client.get("/api/search?q=unknown place")

    assert resp.status_code == 200
    assert resp.json()["normalized_query"] is None


def test_search_requires_q_param():
    client = TestClient(app)
    resp = client.get("/api/search")
    assert resp.status_code == 422


def test_lifespan_builds_es_client_with_timeout_and_closes_it():
    with patch("api.main.Elasticsearch") as MockES, TestClient(app):
        MockES.assert_called_once_with(ES_HOST, request_timeout=10)
        assert app.state.es is MockES.return_value
    MockES.return_value.close.assert_called_once()


def test_search_queries_explicit_fields_and_hides_raw_text(mock_es):
    mock_db = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    mock_es.msearch.return_value = _make_es_response({})
    app.dependency_overrides[get_db] = lambda: mock_db

    TestClient(app).get("/api/search?q=theft")

    searches = mock_es.msearch.call_args.kwargs["searches"]
    bodies = {
        header["index"]: body
        for header, body in zip(searches[::2], searches[1::2], strict=True)
    }
    for body in bodies.values():
        assert "*" not in body["query"]["multi_match"]["fields"]
        assert body["_source"] == {"excludes": ["raw_text", "owner_address"]}
    assert "raw_text" in bodies["incidents"]["query"]["multi_match"]["fields"]
    assert "owner^2" in bodies["properties"]["query"]["multi_match"]["fields"]


def test_search_skips_index_that_returns_an_error(mock_es):
    mock_db = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    es_response = _make_es_response(
        {"incidents": [{"id": 10, "location": "304 HANOVER ST"}]}
    )
    es_response["responses"][0] = {
        "error": {"type": "index_not_found_exception"},
        "status": 404,
    }
    mock_es.msearch.return_value = es_response
    app.dependency_overrides[get_db] = lambda: mock_db

    resp = TestClient(app).get("/api/search?q=304+Hanover+St")

    assert resp.status_code == 200
    results = resp.json()["results"]
    assert results["properties"] == []
    assert results["incidents"][0]["id"] == 10
