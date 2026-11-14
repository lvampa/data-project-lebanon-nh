"""The street list the location prompt carries, and the version that follows it."""

import hashlib
from collections.abc import Iterable


def street_list_version(streets: Iterable[str]) -> str:
    """The first 8 hex digits of the SHA-256 of the sorted streets, one per line."""
    joined = "\n".join(sorted(streets))
    return hashlib.sha256(joined.encode()).hexdigest()[:8]
