from unittest.mock import MagicMock, patch

from api.geocoding import geocode_nominatim


def test_geocode_returns_lat_lng_on_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = [{"lat": "43.6425", "lon": "-72.2518"}]
    with patch("api.geocoding.httpx.get", return_value=mock_resp):
        lat, lng = geocode_nominatim("Main Street")
    assert lat == 43.6425
    assert lng == -72.2518


def test_geocode_returns_none_when_no_results():
    mock_resp = MagicMock()
    mock_resp.json.return_value = []
    with patch("api.geocoding.httpx.get", return_value=mock_resp):
        lat, lng = geocode_nominatim("Unknown Place XYZ")
    assert lat is None
    assert lng is None


def test_geocode_returns_none_on_network_error():
    with patch("api.geocoding.httpx.get", side_effect=Exception("timeout")):
        lat, lng = geocode_nominatim("Anywhere")
    assert lat is None
    assert lng is None
