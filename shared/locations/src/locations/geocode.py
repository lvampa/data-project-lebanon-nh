"""Look a place up on Nominatim, shared by the admin API and the geocode job.

No match, or a reply that cannot be read, is a miss and returns None. A transport
failure or a refusal raises GeocodeUnavailable, which is not a miss. Nominatim's
usage policy allows one request per second, so every lookup goes through a limiter.
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

Precision = Literal["exact", "approximate"]

# A coarse box around Lebanon, NH, cut short of downtown Hanover. It is only a sanity
# check, such as for a street of the same name in another state. It cannot tell West
# Lebanon from White River Junction across the river, so the address decides.
_MIN_LAT, _MAX_LAT = 43.56, 43.69
_MIN_LNG, _MAX_LNG = -72.34, -72.17
# OpenStreetMap may tag West Lebanon as a village of its own, with no "Lebanon" at all.
_AREA_KEYS = ("city", "town", "village", "hamlet")
_AREA_NAMES = frozenset({"Lebanon", "West Lebanon"})


class GeocodeUnavailable(Exception):
    """Nominatim could not be reached or refused the request, so nothing is known about
    the query. That is not a miss: a caller must not count it against the address."""


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
    (limiter or _LIMITER).wait()
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
            timeout=10,
        )
        reply.raise_for_status()
        results = reply.json()
        if results and _is_in_lebanon(results[0]):
            return _result_of(results[0])
    except httpx.HTTPError as exc:
        # Covers timeouts, DNS and connection failures, and a 403 or 429 status.
        raise GeocodeUnavailable(f"geocode({query!r}): {exc}") from exc
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("geocode(%r) got an unreadable reply: %s", query, exc)
    return None


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
