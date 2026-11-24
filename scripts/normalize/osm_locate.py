"""Place a normalized location from the OpenStreetMap snapshot.

A house address and an intersection are settled by code. A named place gets a short list
of real features near its street, and the AI picks one or none. See `place_match`.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import logfire
from locations.canonical import canonical_address, split_house_number, strip_unit
from locations.osm import (
    Candidate,
    Match,
    Snapshot,
    locate_address,
    locate_intersection,
    locate_road,
    place_candidates,
)
from postgres.models.address_normalization import AddressNormalization

from scripts.normalize.backends import AiBackendUnavailable, AiCallFailed

MAX_LLM_CALLS = 100

# (log name, street, candidates) to the one the model chose, or None.
Picker = Callable[[str, str, Sequence[Candidate]], Candidate | None]


@dataclass
class OsmLocator:
    snapshot: Snapshot
    # None when the run has no AI: addresses and intersections are still placed.
    picker: Picker | None = None
    max_llm_calls: int = MAX_LLM_CALLS
    llm_calls: int = 0
    # Places that had candidates but no AI call was made for, because of the cap or a
    # backend that stopped. They wait for the next run.
    left_for_next_run: int = 0
    llm_stopped: bool = False
    # Lookups that came back empty without a real answer: no AI to ask, the cap, a backend
    # that stopped, or a call that failed. A miss with none of these is a real "no".
    unanswered: int = 0

    def locate(self, row: AddressNormalization) -> Match | None:
        normalized = row.normalized_address or ""
        if row.kind == "intersection":
            return self._intersection(normalized)
        if row.kind in ("address", "place"):
            return self._address_or_place(row, normalized)
        return None

    def locate_highway(self, row: AddressNormalization) -> Match | None:
        """An approximate point on the road a bare highway row names, as a bare street gets
        one. The job calls this only for a highway that names no exit and no cross street."""
        for text in (row.street, row.normalized_address):
            if text and (found := locate_road(self.snapshot, text)) is not None:
                return found
        return None

    def _intersection(self, normalized: str) -> Match | None:
        streets = [part.strip() for part in normalized.split(" and ")]
        if len(streets) != 2 or not all(streets):
            return None
        return locate_intersection(self.snapshot, streets[0], streets[1])

    def _address_or_place(
        self, row: AddressNormalization, normalized: str
    ) -> Match | None:
        # "Hannaford, 70 Market St" is a place with a name. "8 Commerce Ave" has none.
        name, _, address = normalized.rpartition(", ")
        number, street = split_house_number(strip_unit(canonical_address(address))[0])
        if number:
            found = locate_address(self.snapshot, number, street)
            if found is not None:
                return found
            if self.snapshot.features_at(number, street):
                logfire.info(
                    "osm: more than one building at {number} {street}, not placed",
                    number=number,
                    street=street,
                )
        if not name or not row.street:
            return None
        return self._place(name, row.street)

    def _place(self, name: str, street: str) -> Match | None:
        candidates = place_candidates(self.snapshot, name, street)
        if not candidates:
            return None
        if self.picker is None:
            self.unanswered += 1
            return None
        if self.llm_stopped or self.llm_calls >= self.max_llm_calls:
            self.left_for_next_run += 1
            self.unanswered += 1
            return None
        self.llm_calls += 1
        try:
            chosen = self.picker(name, street, candidates)
        except AiBackendUnavailable as exc:
            self.llm_stopped = True
            self.left_for_next_run += 1
            self.unanswered += 1
            logfire.error(
                "ai backend unavailable; no more place matches", error=str(exc)
            )
            return None
        except AiCallFailed:
            self.unanswered += 1
            return None
        if chosen is None:
            return None
        feature = chosen.feature
        return Match(
            feature.lat,
            feature.lng,
            feature.ref,
            "llm",
            feature.name or "",
            feature.address,
        )
