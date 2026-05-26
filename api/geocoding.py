import httpx


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
            headers={"User-Agent": "lebanon-nh-police-log/1.0"},
            timeout=10,
        )
        r.raise_for_status()
        results = r.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception:
        pass
    return None, None
