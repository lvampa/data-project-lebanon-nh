"""Look a place up on Nominatim, shared by the admin API and the geocode job.

No match, or a reply that cannot be read, is a miss and returns None. A transport
failure or a refusal raises GeocodeUnavailable, which is not a miss. Nominatim's
usage policy allows one request per second, so every lookup goes through a limiter.
A 403 or 429 raises GeocodeBackOff, which a caller must stop on. Any other failure is
transient, and a caller may skip the query. Nothing is tried again here.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx

logger = logging.getLogger(__name__)

_REPO_URL = "https://github.com/lvampa/Data-Project-Lebanon-NH"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim sometimes holds one request for over 10 seconds. Its policy does not mind
# how long the client waits, only how often it asks.
_TIMEOUT_S = 30
# Nominatim is telling the client to stop.
_BACK_OFF_STATUSES = (403, 429)

Precision = Literal["exact", "approximate"]

# A coarse box around Lebanon, NH, cut short of downtown Hanover. It is only a sanity
# check, such as for a street of the same name in another state. It cannot tell West
# Lebanon from White River Junction across the river, so the address decides.
_MIN_LAT, _MAX_LAT = 43.56, 43.69
_MIN_LNG, _MAX_LNG = -72.34, -72.17
# South, west, north, east: the order Overpass wants in a bounding box.
CITY_BBOX = (_MIN_LAT, _MIN_LNG, _MAX_LAT, _MAX_LNG)
# OpenStreetMap may tag West Lebanon as a village of its own, with no "Lebanon" at all.
_AREA_KEYS = ("city", "town", "village", "hamlet")
_AREA_NAMES = frozenset({"Lebanon", "West Lebanon"})


class GeocodeUnavailable(Exception):
    """Nominatim could not be reached or refused the request, so nothing is known about
    the query. That is not a miss: a caller must not count it against the address."""


class GeocodeBackOff(GeocodeUnavailable):
    """Nominatim answered 403 or 429. Asking again risks a ban, so a caller stops. Any
    other GeocodeUnavailable is transient, and a caller may skip that query."""


@dataclass(frozen=True)
class GeocodeResult:
    lat: float
    lng: float
    precision: Precision


def in_city_bounds(lat: float, lng: float) -> bool:
    return _MIN_LAT <= lat <= _MAX_LAT and _MIN_LNG <= lng <= _MAX_LNG


class Waiter(Protocol):
    def wait(self) -> None: ...


class RateLimiter:
    """Holds calls to one per `min_interval_s`, by sleeping before the next one."""

    def __init__(
        self,
        min_interval_s: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._interval = min_interval_s
        self._clock = clock
        self._sleep = sleep
        self._last_call: float | None = None

    def wait(self) -> None:
        if self._last_call is not None:
            remaining = self._interval - (self._clock() - self._last_call)
            if remaining > 0:
                self._sleep(remaining)
        self._last_call = self._clock()


# One limiter for the whole process, so two callers cannot go over the limit together.
_LIMITER = RateLimiter()


def geocode(
    query: str, contact: str | None = None, limiter: Waiter | None = None
) -> GeocodeResult | None:
    """The coordinates of the first Nominatim match for `query`, or None.

    A match outside Lebanon, NH is a miss, so no caller can pin a place in another town.
    """
    reply = _get(query, contact, limiter or _LIMITER)
    try:
        results = reply.json()
        if results and _is_in_lebanon(results[0]):
            return _result_of(results[0])
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("geocode(%r) got an unreadable reply: %s", query, exc)
    return None


def _get(query: str, contact: str | None, limiter: Waiter) -> httpx.Response:
    """The reply to one search. Any failure raises, and nothing is tried again here."""
    limiter.wait()
    try:
        reply = httpx.get(
            _NOMINATIM_URL,
            params={
                "q": query,
                "format": "json",
                "limit": 1,
                "countrycodes": "us",
                "addressdetails": 1,
            },
            headers={"User-Agent": _user_agent(contact)},
            timeout=_TIMEOUT_S,
        )
        reply.raise_for_status()
    except httpx.HTTPStatusError as exc:
        message = f"geocode({query!r}): {exc}"
        if exc.response.status_code in _BACK_OFF_STATUSES:
            raise GeocodeBackOff(message) from exc
        raise GeocodeUnavailable(message) from exc
    except httpx.HTTPError as exc:
        # Covers timeouts, DNS and connection failures.
        raise GeocodeUnavailable(f"geocode({query!r}): {exc}") from exc
    return reply


def _is_in_lebanon(match: dict[str, Any]) -> bool:
    address = match.get("address") or {}
    in_lebanon = address.get("state") == "New Hampshire" and any(
        address.get(key) in _AREA_NAMES for key in _AREA_KEYS
    )
    return in_lebanon and in_city_bounds(float(match["lat"]), float(match["lon"]))


def _result_of(match: dict[str, Any]) -> GeocodeResult:
    return GeocodeResult(
        lat=float(match["lat"]), lng=float(match["lon"]), precision=_precision(match)
    )


def _precision(match: dict[str, Any]) -> Precision:
    """A street or highway comes back as a road way with no point on it, so the
    coordinates are somewhere along it. An address, a place, or an intersection is a
    point or a building."""
    is_road = match.get("class") == "highway" and match.get("osm_type") == "way"
    return "approximate" if is_road else "exact"


def _user_agent(contact: str | None) -> str:
    # Nominatim's usage policy requires a way to reach whoever runs the client.
    return f"lebanon-nh-police-log/1.0 ({contact or _REPO_URL})"
