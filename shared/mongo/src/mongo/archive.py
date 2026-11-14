"""The raw source archive: every downloaded original, kept as it was downloaded.

It is a side copy. A MongoDB problem is logged and counted, never raised, so the
Postgres path runs exactly as it would without the archive.
"""

import gzip
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import logfire
from bson import Binary
from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from .client import MongoDB

COLLECTION = "raw_sources"
RawCollection = Collection[dict[str, Any]]
BATCH_SIZE = 50
# Bodies are compressed in the application; MongoDB's document limit is 16 MB.
MAX_COMPRESSED_BYTES = 15 * 1024 * 1024

# ASP.NET hidden fields on VGSI pages. They change between visits even when the
# parcel does not, so they are left out of the content hash.
_PAGE_STATE_FIELD = re.compile(
    rb'<input[^>]*name="__(?:VIEWSTATE|VIEWSTATEGENERATOR|EVENTVALIDATION)"[^>]*>'
)


@dataclass(frozen=True)
class ArchivedResponse:
    url: str
    status: int
    content_type: str | None
    body: bytes
    fetched_at: datetime
    spider: str
    # Text extracted from the body in a separate step, kept beside it. Budget PDFs.
    text: str | None = None


@dataclass(frozen=True)
class ArchiveCounts:
    stored: int
    seen_again: int
    failed: int


def content_hash(source: str, body: bytes) -> str:
    if source == "vgsi_parcel":
        body = _PAGE_STATE_FIELD.sub(b"", body)
    return hashlib.sha256(body).hexdigest()


def archive_collection(settings: MongoDB) -> RawCollection:
    """The archive collection, on a client that gives up quickly."""
    return quick_collection(settings, COLLECTION)


def quick_collection(settings: MongoDB, name: str) -> RawCollection:
    """A collection on a client that gives up quickly.

    Two seconds to find and connect to a server, and five for any one read or write
    on the socket, so a server that accepts the connection and then hangs cannot
    stop a crawl. These are per-socket limits on purpose: pymongo's timeoutMS, and
    pymongo.timeout(), would also cover server selection and override its 2 seconds.
    """
    client: MongoClient[dict[str, Any]] = MongoClient(
        host=settings.host,
        port=settings.port,
        username=settings.username,
        password=settings.password,
        serverSelectionTimeoutMS=2000,
        connectTimeoutMS=2000,
        socketTimeoutMS=5000,
    )
    return client[settings.default_db][name]


def is_unreachable(exc: PyMongoError) -> bool:
    """Whether an error means the server is gone, so later writes would only wait."""
    return isinstance(exc, ServerSelectionTimeoutError) or exc.timeout


class RawArchive:
    def __init__(self, collection: RawCollection, batch_size: int = BATCH_SIZE) -> None:
        self._collection = collection
        self._batch_size = batch_size
        self._buffer: list[UpdateOne] = []
        self._stored = self._seen_again = self._failed = 0
        self.is_down = False

    def add(
        self, source: str, source_key: str, response: ArchivedResponse
    ) -> bool | None:
        """Buffer one version, and write the buffer once it holds a full batch.

        Returns whether that write worked, or None while the version is still
        buffered. With a batch size of 1 every call writes, so the caller knows.
        """
        self._buffer.append(_upsert_version(source, source_key, response))
        if len(self._buffer) < self._batch_size:
            return None
        return self._write_buffer()

    def flush(self) -> ArchiveCounts:
        """Write what is buffered, and return the counts for the run so far."""
        self._write_buffer()
        return ArchiveCounts(self._stored, self._seen_again, self._failed)

    def _write_buffer(self) -> bool:
        batch = self._buffer
        self._buffer = []
        if not batch:
            return True
        if self.is_down:
            self._failed += len(batch)
            return False
        return self._write(batch)

    def _write(self, batch: list[UpdateOne]) -> bool:
        try:
            result = self._collection.bulk_write(batch, ordered=False)
        except PyMongoError as exc:
            self._failed += len(batch)
            if is_unreachable(exc):
                self.is_down = True
                logfire.error(
                    "raw archive unreachable; dropping its writes for this run",
                    error=repr(exc),
                )
            else:
                logfire.warning("raw archive batch failed", error=repr(exc))
            return False
        self._stored += result.upserted_count
        self._seen_again += result.matched_count
        return True

    # Reads are for operator commands and reprocess, not the crawl, so a MongoDB
    # error is raised to the caller instead of counted.

    def keys(self, source: str) -> list[str]:
        """Every source key with at least one version, in sorted order."""
        return sorted(self._collection.distinct("source_key", {"source": source}))

    def versions(self, source: str, source_key: str) -> list[dict[str, Any]]:
        """Every version of one source key, newest first."""
        return list(
            self._collection.find({"source": source, "source_key": source_key}).sort(
                "first_fetched_at", -1
            )
        )

    def newest(self, source: str, source_key: str) -> dict[str, Any] | None:
        return self._collection.find_one(
            {"source": source, "source_key": source_key},
            sort=[("first_fetched_at", -1)],
        )

    def by_hash(
        self, source: str, source_key: str, content_hash: str
    ) -> dict[str, Any] | None:
        return self._collection.find_one(
            {"source": source, "source_key": source_key, "content_hash": content_hash}
        )


def stored_body(version: dict[str, Any]) -> bytes | None:
    """A version's body as downloaded, or None when it was too large to keep."""
    if version.get("truncated"):
        return None
    return gzip.decompress(version["body_gzip"])


def _upsert_version(
    source: str, source_key: str, response: ArchivedResponse
) -> UpdateOne:
    """One write that stores a new version, or records a repeat of a stored one."""
    first_fetch: dict[str, Any] = {
        "url": response.url,
        "status": response.status,
        "content_type": response.content_type,
        "size_bytes": len(response.body),
        "first_fetched_at": response.fetched_at,
        "spider": response.spider,
        **_compressed_body(source_key, response.body),
    }
    if response.text is not None:
        first_fetch["text_gzip"] = Binary(gzip.compress(response.text.encode()))
    return UpdateOne(
        {
            "source": source,
            "source_key": source_key,
            "content_hash": content_hash(source, response.body),
        },
        {
            "$setOnInsert": first_fetch,
            "$set": {"last_seen_at": response.fetched_at},
            "$inc": {"seen_count": 1},
        },
        upsert=True,
    )


def _compressed_body(source_key: str, body: bytes) -> dict[str, Any]:
    compressed = gzip.compress(body)
    if len(compressed) > MAX_COMPRESSED_BYTES:
        logfire.warning(
            "raw archive body too large; storing the version without it",
            source_key=source_key,
            compressed_bytes=len(compressed),
        )
        return {"truncated": True}
    return {"body_gzip": Binary(compressed), "truncated": False}
