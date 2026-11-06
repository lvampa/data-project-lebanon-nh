import pytest

PAGED_ROUTES = ["/api/incidents", "/api/addresses", "/api/categories", "/api/llcs"]


@pytest.mark.parametrize("route", PAGED_ROUTES)
@pytest.mark.parametrize("query", ["page=0", "per_page=0", "per_page=201"])
def test_list_routes_reject_out_of_range_paging(mock_db, client, route, query):
    resp = client.get(f"{route}?{query}")

    assert resp.status_code == 422
    mock_db.execute.assert_not_called()
    mock_db.scalars.assert_not_called()
