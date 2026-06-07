import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from models.url_record import UrlRecord


def make_url(**kwargs):
    defaults = dict(
        canonical_url="https://example.com/log.pdf",
        archive_url=None,
        log_date=None,
        state="pending",
        created_at=datetime.now(timezone.utc),
    )
    return {**defaults, **kwargs}


def test_url_record_shape():
    record = UrlRecord.model_validate(make_url())
    assert record.canonical_url == "https://example.com/log.pdf"
    assert record.state == "pending"


def test_url_record_null_optional_fields():
    record = UrlRecord.model_validate(make_url(archive_url=None, log_date=None))
    assert record.archive_url is None
    assert record.log_date is None


def test_url_record_missing_canonical_url_raises():
    data = make_url()
    del data["canonical_url"]
    with pytest.raises(ValidationError):
        UrlRecord.model_validate(data)


def test_url_record_blank_canonical_url_raises():
    with pytest.raises(ValidationError):
        UrlRecord.model_validate(make_url(canonical_url=""))


def test_url_record_invalid_state_raises():
    with pytest.raises(ValidationError):
        UrlRecord.model_validate(make_url(state="invalid"))


def test_url_record_valid_states():
    for state in ("pending", "in_progress", "complete", "error"):
        record = UrlRecord.model_validate(make_url(state=state))
        assert record.state == state
