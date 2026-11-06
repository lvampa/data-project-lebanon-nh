import logging
import os

import httpx

logger = logging.getLogger(__name__)

_REPO_URL = "https://github.com/lvampa/Data-Project-Lebanon-NH"


def _user_agent() -> str:
    # Nominatim's usage policy requires a way to reach whoever runs the client.
    contact = os.environ.get("NOMINATIM_CONTACT") or _REPO_URL
    return f"lebanon-nh-police-log/1.0 ({contact})"


def geocode_nominatim(address: str) -> tuple[float | None, float | None]:
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
            headers={"User-Agent": _user_agent()},
            timeout=10,
        )
        r.raise_for_status()
        results = r.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as exc:
        logger.warning("geocode_nominatim(%r) failed: %s", address, exc)
    return None, None
