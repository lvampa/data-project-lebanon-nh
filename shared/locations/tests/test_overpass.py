import httpx
import pytest
from locations.overpass import (
    FEATURES_QUERY,
    RETRY_WAITS_S,
    ROADS_QUERY,
    OverpassUnavailable,
    overpass_query,
)

GOOD = {"elements": [{"type": "node", "id": 1}]}


class FakePost:
    """Plays one scripted reply per call: a status, a response, or an exception."""

    def __init__(self, *replies: object) -> None:
        self.replies = list(replies)
        self.calls = 0

    def __call__(self, url: str, **kwargs: object) -> httpx.Response:
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, int):
            return httpx.Response(reply, text="busy")
        if isinstance(reply, str):
            return httpx.Response(200, text=reply)
        return httpx.Response(200, json=reply)


def run(*replies: object):
    waits: list[float] = []
    post = FakePost(*replies)
    return post, waits, lambda: overpass_query("q", sleep=waits.append, post=post)


def test_a_good_reply_is_returned_without_waiting():
    post, waits, call = run(GOOD)

    assert call() == GOOD
    assert (post.calls, waits) == (1, [])


def test_a_busy_server_is_retried_with_longer_waits():
    post, waits, call = run(502, 429, 504, GOOD)

    assert call() == GOOD
    assert waits == [10, 30, 90]


def test_it_fails_with_the_last_status_after_the_retries():
    post, waits, call = run(502, 502, 502, 502, 502)

    with pytest.raises(OverpassUnavailable, match="HTTP 502"):
        call()
    assert waits == list(RETRY_WAITS_S)
    assert post.calls == 5


def test_a_timeout_is_retried():
    _, waits, call = run(httpx.ReadTimeout("slow"), GOOD)

    assert call() == GOOD
    assert waits == [10]


def test_an_unreadable_reply_is_retried():
    _, waits, call = run("<html>runtime error</html>", GOOD)

    assert call() == GOOD
    assert waits == [10]


def test_another_error_status_is_not_retried():
    post, waits, call = run(400)

    with pytest.raises(OverpassUnavailable, match="HTTP 400"):
        call()
    assert (post.calls, waits) == (1, [])


def test_both_queries_are_scoped_to_the_city_boundary():
    for query in (FEATURES_QUERY, ROADS_QUERY):
        assert '["admin_level"="8"]["name"="Lebanon"]' in query
        assert "map_to_area->.city" in query
        assert "(area.city)" in query


def test_the_roads_query_takes_ways_with_a_route_number_and_no_name():
    assert '["highway"]["name"]' in ROADS_QUERY
    assert '["highway"]["ref"]' in ROADS_QUERY
