"""Download OpenStreetMap data for Lebanon, NH from Overpass, for the geocode job.

The queries are scoped to the city's own boundary, not to a box. A box around Lebanon
takes in White River Junction, Vermont, where Bridge, Maple and Main Street also exist.

Overpass is a shared service that answers 429 or 502 when it is busy, so a request is
tried again a few times with a longer wait each time. Then it fails with the last
status, and the caller decides what to do.
"""

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from locations.geocode import CITY_BBOX

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_REPO_URL = "https://github.com/lvampa/Data-Project-Lebanon-NH"
_TIMEOUT_S = 180
_RETRY_STATUSES = (429, 502, 503, 504)
RETRY_WAITS_S = (10, 30, 90, 180)

_BBOX = ",".join(str(value) for value in CITY_BBOX)
# Lebanon is a city, admin level 8. The box only picks it out from the many other towns
# called Lebanon, and `map_to_area` turns its relation into the area the rest filters on.
_CITY_AREA = (
    f'rel["boundary"="administrative"]["admin_level"="8"]["name"="Lebanon"]({_BBOX});'
    "map_to_area->.city;"
)

# Everything with a name or a house number, with a center point for a way or a relation.
FEATURES_QUERY = f"""\
[out:json][timeout:{_TIMEOUT_S}];
{_CITY_AREA}
(
  nwr(area.city)["name"];
  nwr(area.city)["addr:housenumber"];
);
out tags center;"""

# Named roads, with the id and position of every node on them.
ROADS_QUERY = f"""\
[out:json][timeout:{_TIMEOUT_S}];
{_CITY_AREA}
way(area.city)["highway"]["name"];
out geom;"""


class OverpassUnavailable(Exception):
    """Overpass could not be reached or kept answering that it was busy."""


Poster = Callable[..., httpx.Response]


def overpass_query(
    query: str,
    *,
    contact: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
    post: Poster = httpx.post,
) -> dict[str, Any]:
    """The JSON reply to one query, after up to four retries."""
    last_problem = ""
    for attempt, wait in enumerate((0, *RETRY_WAITS_S)):
        if wait:
            logger.warning(
                "overpass: %s, trying again in %s s (retry %s)",
                last_problem,
                wait,
                attempt,
            )
            sleep(wait)
        try:
            reply = post(
                OVERPASS_URL,
                data={"data": query},
                headers={"User-Agent": _user_agent(contact)},
                timeout=_TIMEOUT_S,
            )
        except httpx.HTTPError as exc:
            last_problem = f"request failed: {exc}"
            continue
        if reply.status_code in _RETRY_STATUSES:
            last_problem = f"HTTP {reply.status_code}"
            continue
        if reply.status_code != 200:
            raise OverpassUnavailable(f"Overpass answered HTTP {reply.status_code}.")
        try:
            body = reply.json()
        except ValueError:
            last_problem = "unreadable reply"
            continue
        if isinstance(body, dict) and "elements" in body:
            return body
        last_problem = "reply without elements"
    raise OverpassUnavailable(
        f"Overpass kept failing after {len(RETRY_WAITS_S)} retries: {last_problem}."
    )


def _user_agent(contact: str | None) -> str:
    return f"lebanon-nh-police-log/1.0 ({contact or _REPO_URL})"
