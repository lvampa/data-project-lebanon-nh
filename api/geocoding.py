import logging

import httpx

logger = logging.getLogger(__name__)

_REPO_URL = "https://github.com/lvampa/Data-Project-Lebanon-NH"


def _user_agent(contact: str | None) -> str:
    # Nominatim's usage policy requires a way to reach whoever runs the client.
    return f"lebanon-nh-police-log/1.0 ({contact or _REPO_URL})"


def geocode_nominatim(
    address: str, contact: str | None = None
) -> tuple[float | None, float | None]:
    """Query Nominatim for lat/lng. Returns (None, None) on any failure."""
    try:
        r = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": f"{address}, Lebanon, NH, USA",
                "format": "json",
                "limit": 1,
                "countrycodes": "us",
            },
            headers={"User-Agent": _user_agent(contact)},
            timeout=10,
        )
        r.raise_for_status()
        results = r.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as exc:
        logger.warning("geocode_nominatim(%r) failed: %s", address, exc)
    return None, None
