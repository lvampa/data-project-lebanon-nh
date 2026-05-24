from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from models.url_document import UrlDocument


def test_requires_canonical_url():
    doc = UrlDocument(
        canonical_url="https://example.com/a.pdf",
        state="pending",
        created_at=datetime.now(timezone.utc),
    )
    assert doc.canonical_url == "https://example.com/a.pdf"


def test_archive_url_optional():
    doc = UrlDocument(
        canonical_url="https://example.com/a.pdf",
        state="pending",
        created_at=datetime.now(timezone.utc),
    )
    assert doc.archive_url is None


def test_archive_url_stored():
    doc = UrlDocument(
        canonical_url="https://example.com/a.pdf",
        archive_url="https://web.archive.org/web/20191015/https://example.com/a.pdf",
        state="pending",
        created_at=datetime.now(timezone.utc),
    )
    assert doc.archive_url == "https://web.archive.org/web/20191015/https://example.com/a.pdf"


def test_raw_text_optional():
    doc = UrlDocument(
        canonical_url="https://example.com/a.pdf",
        state="pending",
        created_at=datetime.now(timezone.utc),
    )
    assert doc.raw_text is None


def test_valid_states():
    for state in ("pending", "complete", "error"):
        doc = UrlDocument(
            canonical_url="https://example.com/a.pdf",
            state=state,
            created_at=datetime.now(timezone.utc),
        )
        assert doc.state == state


def test_invalid_state_raises():
    with pytest.raises(ValidationError):
        UrlDocument(
            canonical_url="https://example.com/a.pdf",
            state="downloaded",
            created_at=datetime.now(timezone.utc),
        )
