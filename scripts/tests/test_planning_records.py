from datetime import datetime

import pytest
from pydantic import ValidationError

from scripts.models import PlanningDocumentRecord, PlanningMeetingRecord

SCRAPED_AT = datetime(2026, 10, 31, 6, 0, 0)


def test_meeting_record_accepts_parsed_event():
    record = PlanningMeetingRecord.model_validate(
        {
            "civicclerk_event_id": 2521,
            "title": " Planning Board Regular Meeting ",
            "category": "Planning Board",
            "meeting_date": datetime(2024, 3, 5, 18, 0, 0),
            "location": None,
            "status": "Final",
            "source_url": "https://lebanonh.portal.civicclerk.com/event/2521",
            "scraped_at": SCRAPED_AT,
        }
    )
    assert record.title == "Planning Board Regular Meeting"
    assert record.location is None


def test_meeting_record_requires_source_url():
    with pytest.raises(ValidationError, match="source_url"):
        PlanningMeetingRecord.model_validate(
            {"civicclerk_event_id": 2521, "source_url": "", "scraped_at": SCRAPED_AT}
        )


def test_meeting_record_rejects_non_integer_event_id():
    with pytest.raises(ValidationError, match="civicclerk_event_id"):
        PlanningMeetingRecord.model_validate(
            {
                "civicclerk_event_id": "abc",
                "source_url": "https://example.com",
                "scraped_at": SCRAPED_AT,
            }
        )


def test_document_record_defaults_raw_text_to_none():
    record = PlanningDocumentRecord.model_validate(
        {
            "civicclerk_file_id": 8184,
            "civicclerk_event_id": 2521,
            "file_name": "Agenda.pdf",
            "file_type": "Agenda",
            "download_url": "https://example.com/file.pdf",
            "scraped_at": SCRAPED_AT,
        }
    )
    assert record.raw_text is None


def test_document_record_requires_event_id():
    with pytest.raises(ValidationError, match="civicclerk_event_id"):
        PlanningDocumentRecord.model_validate(
            {"civicclerk_file_id": 8184, "scraped_at": SCRAPED_AT}
        )
