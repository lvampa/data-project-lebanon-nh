"""The street list the location prompt carries, and the version that follows it.

It is built from the parcel locations, which are the one list of real Lebanon, NH
street addresses the project has. It depends on the VGSI scrape having run: an empty
`properties` table gives an empty list, and the job then makes no location AI calls.
"""

import hashlib
from collections.abc import Iterable

from locations.canonical import canonical_address, split_house_number, strip_unit
from postgres.models.property import Property
from sqlalchemy import select
from sqlalchemy.orm import Session


def streets_from_locations(locations: Iterable[str | None]) -> list[str]:
    """Distinct canonical streets, sorted, with house numbers and units removed."""
    streets: set[str] = set()
    for location in locations:
        if not location or not location.strip():
            continue
        without_unit, _ = strip_unit(canonical_address(location))
        _, street = split_house_number(without_unit)
        if street:
            streets.add(street)
    return sorted(streets)


def load_street_list(session: Session) -> list[str]:
    """The street list, built once per run from `properties.location`."""
    return streets_from_locations(
        session.scalars(select(Property.location).where(Property.location.is_not(None)))
    )


def street_list_version(streets: Iterable[str]) -> str:
    """The first 8 hex digits of the SHA-256 of the sorted streets, one per line."""
    joined = "\n".join(sorted(streets))
    return hashlib.sha256(joined.encode()).hexdigest()[:8]
