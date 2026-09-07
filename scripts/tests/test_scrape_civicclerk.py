from datetime import datetime

from scripts.scrape.scrape_civicclerk import (
    extract_text_from_pdf,
    parse_event,
    parse_file,
)

EVENT_JSON = {
    "id": 2521,
    "title": "Planning Board Regular Meeting",
    "eventGroupId": 5,
    "eventStartDate": "2024-03-05T18:00:00",
    "location": "City Hall, 51 North Park Street",
    "status": {"description": "Final"},
}

FILE_JSON = {
    "id": 8184,
    "name": "Agenda - March 5 2024.pdf",
    "fileType": 1,
    "streamUrl": None,
}


def test_parse_event_extracts_fields():
    result = parse_event(EVENT_JSON, category_name="Planning Board")
    assert result["civicclerk_event_id"] == 2521
    assert result["title"] == "Planning Board Regular Meeting"
    assert result["category"] == "Planning Board"
    assert result["meeting_date"] == datetime(2024, 3, 5, 18, 0, 0)
    assert result["location"] == "City Hall, 51 North Park Street"
    assert result["status"] == "Final"
    assert result["source_url"] == "https://lebanonh.portal.civicclerk.com/event/2521"


def test_parse_event_handles_missing_status():
    data = {**EVENT_JSON, "status": None}
    result = parse_event(data, category_name="Planning Board")
    assert result["status"] is None


def test_parse_event_handles_bad_date():
    data = {**EVENT_JSON, "eventStartDate": "not-a-date"}
    result = parse_event(data, category_name="Planning Board")
    assert result["meeting_date"] is None


def test_parse_file_maps_type_int_to_string():
    result = parse_file(FILE_JSON, event_id=2521)
    assert result["civicclerk_file_id"] == 8184
    assert result["civicclerk_event_id"] == 2521
    assert result["file_name"] == "Agenda - March 5 2024.pdf"
    assert result["file_type"] == "Agenda"
    assert (
        result["download_url"]
        == "https://lebanonh.api.civicclerk.com/v1/Events/GetEventFileStream(fileId=8184,fileType=1,plainText=false)"
    )


def test_parse_file_uses_stream_url_when_present():
    data = {**FILE_JSON, "streamUrl": "https://cdn.example.com/file.pdf"}
    result = parse_file(data, event_id=2521)
    assert result["download_url"] == "https://cdn.example.com/file.pdf"


def test_extract_text_from_pdf_returns_none_for_non_pdf():
    result = extract_text_from_pdf(b"this is not a pdf")
    assert result is None


def test_extract_text_from_pdf_returns_none_for_empty_bytes():
    result = extract_text_from_pdf(b"")
    assert result is None
