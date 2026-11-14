from unittest.mock import MagicMock, patch

import pytest
from locations.geocode import GeocodeResult, RateLimiter, geocode, in_city_bounds

LEBANON_CENTER = (43.6426, -72.2518)


LEBANON_ADDRESS = {"city": "Lebanon", "state": "New Hampshire"}


def nominatim_reply(**fields: object) -> MagicMock:
    reply = MagicMock()
    reply.json.return_value = [
        {
            "lat": "43.6425",
            "lon": "-72.2518",
            "osm_type": "node",
            "class": "place",
            "address": LEBANON_ADDRESS,
            **fields,
        }
    ]
    return reply


class NoWait:
    """A limiter that never sleeps, so these tests do not take a second each."""

    def __init__(self) -> None:
        self.waits = 0

    def wait(self) -> None:
        self.waits += 1


def look_up(query: str = "12 Main St, Lebanon, NH", **kwargs) -> GeocodeResult | None:
    return geocode(query, limiter=NoWait(), **kwargs)


def found(query: str = "12 Main St, Lebanon, NH") -> GeocodeResult:
    result = look_up(query)
    assert result is not None, "expected a match"
    return result


# --- the result ---


def test_a_matched_address_is_an_exact_result():
    reply = nominatim_reply(**{"class": "building", "type": "house", "osm_type": "way"})
    with patch("locations.geocode.httpx.get", return_value=reply):
        result = look_up()

    assert result == GeocodeResult(lat=43.6425, lng=-72.2518, precision="exact")


def test_a_matched_place_is_exact():
    with patch("locations.geocode.httpx.get", return_value=nominatim_reply()):
        assert found().precision == "exact"


def test_an_intersection_node_is_exact():
    reply = nominatim_reply(
        **{"class": "highway", "type": "traffic_signals", "osm_type": "node"}
    )
    with patch("locations.geocode.httpx.get", return_value=reply):
        assert found("Main St and Elm St, Lebanon, NH").precision == "exact"


@pytest.mark.parametrize("road_type", ["residential", "primary", "motorway", "trunk"])
def test_a_street_or_highway_matched_without_a_point_is_approximate(road_type):
    reply = nominatim_reply(
        **{"class": "highway", "type": road_type, "osm_type": "way"}
    )
    with patch("locations.geocode.httpx.get", return_value=reply):
        assert found("Main St, Lebanon, NH").precision == "approximate"


def test_the_query_is_sent_as_given_with_one_result_and_the_us_only():
    with patch("locations.geocode.httpx.get", return_value=nominatim_reply()) as get:
        look_up("Hannaford, Market St, Lebanon, NH")

    params = get.call_args.kwargs["params"]
    assert params == {
        "q": "Hannaford, Market St, Lebanon, NH",
        "format": "json",
        "limit": 1,
        "countrycodes": "us",
        "addressdetails": 1,
    }


# --- failures are a miss, never an exception ---


def test_no_results_is_a_miss():
    reply = MagicMock()
    reply.json.return_value = []
    with patch("locations.geocode.httpx.get", return_value=reply):
        assert look_up("Unknown Place XYZ") is None


def test_a_network_error_is_a_miss():
    with patch("locations.geocode.httpx.get", side_effect=Exception("timeout")):
        assert look_up() is None


def test_a_reply_with_no_coordinates_is_a_miss():
    reply = MagicMock()
    reply.json.return_value = [{"osm_type": "way"}]
    with patch("locations.geocode.httpx.get", return_value=reply):
        assert look_up() is None


def test_a_bad_http_status_is_a_miss():
    reply = MagicMock()
    reply.raise_for_status.side_effect = Exception("429")
    with patch("locations.geocode.httpx.get", return_value=reply):
        assert look_up() is None


# --- the user agent ---


def test_the_user_agent_includes_the_contact():
    with patch("locations.geocode.httpx.get", return_value=nominatim_reply()) as get:
        look_up(contact="ops@example.com")

    assert "ops@example.com" in get.call_args.kwargs["headers"]["User-Agent"]


@pytest.mark.parametrize("contact", [None, ""])
def test_the_user_agent_falls_back_to_the_repo(contact):
    with patch("locations.geocode.httpx.get", return_value=nominatim_reply()) as get:
        look_up(contact=contact)

    assert "github.com/" in get.call_args.kwargs["headers"]["User-Agent"]


# --- only Lebanon, NH counts (6.4) ---


def test_the_request_asks_for_address_details():
    with patch("locations.geocode.httpx.get", return_value=nominatim_reply()) as get:
        look_up()

    assert get.call_args.kwargs["params"]["addressdetails"] == 1


@pytest.mark.parametrize("area", ["city", "town"])
def test_a_match_in_lebanon_nh_counts_whether_nominatim_calls_it_a_city_or_town(area):
    reply = nominatim_reply(address={area: "Lebanon", "state": "New Hampshire"})
    with patch("locations.geocode.httpx.get", return_value=reply):
        assert look_up() is not None


@pytest.mark.parametrize(
    ("place", "address", "lat", "lng"),
    [
        # Hanover is a town over, and the box cannot tell the two apart near the line.
        ("Hanover, NH", {"town": "Hanover", "state": "New Hampshire"}, 43.68, -72.29),
        # The river separates West Lebanon from White River Junction by a few hundred meters.
        (
            "White River Junction, VT",
            {"town": "Hartford", "state": "Vermont"},
            43.65,
            -72.32,
        ),
        # Lebanon, but the one in Maine.
        ("Lebanon, ME", {"town": "Lebanon", "state": "Maine"}, 43.64, -72.25),
        ("no address given", None, 43.64, -72.25),
    ],
)
def test_a_match_in_another_town_is_a_miss_even_inside_the_box(
    place, address, lat, lng
):
    reply = nominatim_reply(lat=str(lat), lon=str(lng), address=address)
    with patch("locations.geocode.httpx.get", return_value=reply):
        assert look_up() is None, place


def test_a_match_outside_the_box_is_a_miss_even_when_it_says_lebanon_nh():
    reply = nominatim_reply(lat="43.2081", lon="-71.5376")
    with patch("locations.geocode.httpx.get", return_value=reply):
        assert look_up() is None


# --- the city bounds (6.4) ---


def test_the_city_center_is_inside_the_bounds():
    assert in_city_bounds(*LEBANON_CENTER)


@pytest.mark.parametrize(
    ("place", "lat", "lng"),
    [
        ("Concord, NH", 43.2081, -71.5376),
        ("Boston", 42.3601, -71.0589),
        ("White River Junction, VT", 43.6489, -72.42),
        ("downtown Hanover, NH", 43.7022, -72.2896),
        ("north of the city", 43.80, -72.25),
        ("south of the city", 43.50, -72.25),
    ],
)
def test_places_outside_the_city_are_outside_the_bounds(place, lat, lng):
    assert not in_city_bounds(lat, lng), place


# --- one request per second (6.7) ---


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_the_first_request_does_not_wait():
    clock = FakeClock()
    limiter = RateLimiter(1.0, clock=clock.time, sleep=clock.sleep)

    limiter.wait()

    assert clock.slept == []


def test_a_request_right_after_another_waits_out_the_second():
    clock = FakeClock()
    limiter = RateLimiter(1.0, clock=clock.time, sleep=clock.sleep)
    limiter.wait()
    clock.now += 0.25

    limiter.wait()

    assert clock.slept == [pytest.approx(0.75)]


def test_a_request_after_a_full_second_does_not_wait():
    clock = FakeClock()
    limiter = RateLimiter(1.0, clock=clock.time, sleep=clock.sleep)
    limiter.wait()
    clock.now += 1.5

    limiter.wait()

    assert clock.slept == []


def test_every_lookup_waits_for_the_limiter_first():
    limiter = NoWait()
    with patch("locations.geocode.httpx.get", return_value=nominatim_reply()):
        geocode("a, Lebanon, NH", limiter=limiter)
        geocode("b, Lebanon, NH", limiter=limiter)

    assert limiter.waits == 2


def test_a_failed_lookup_still_counts_against_the_limit():
    limiter = NoWait()
    with patch("locations.geocode.httpx.get", side_effect=Exception("down")):
        geocode("a, Lebanon, NH", limiter=limiter)

    assert limiter.waits == 1
