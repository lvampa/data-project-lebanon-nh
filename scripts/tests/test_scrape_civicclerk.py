import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

from sqlalchemy.dialects import postgresql

from scripts.models import PlanningDocumentRecord
from scripts.scrape import scrape_civicclerk
from scripts.scrape.scrape_civicclerk import (
    extract_text_from_pdf,
    parse_event,
    parse_file,
    save_event,
    upsert_document,
)

SCRAPED_AT = datetime(2026, 10, 31, 6, 0, 0)

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


def test_extract_text_from_pdf_logs_parse_failures():
    with patch.object(scrape_civicclerk.logfire, "warning") as warning:
        result = extract_text_from_pdf(b"%PDF-1.7 truncated garbage")
    assert result is None
    warning.assert_called_once()


# --- write path ---


def conflict_set_clause(statement) -> str:
    sql = str(statement.compile(dialect=postgresql.dialect()))
    return sql.split("ON CONFLICT", 1)[1]


def document(raw_text: str | None) -> PlanningDocumentRecord:
    return PlanningDocumentRecord(
        civicclerk_file_id=8184,
        civicclerk_event_id=2521,
        file_name="Agenda.pdf",
        file_type="Agenda",
        download_url="https://example.com/file.pdf",
        raw_text=raw_text,
        scraped_at=SCRAPED_AT,
    )


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    async def body(self) -> bytes:
        return self._body


class FakeRequestContext:
    def __init__(self, body: bytes = b"", fail: bool = False) -> None:
        self.body = body
        self.fail = fail
        self.urls: list[str] = []

    async def get(self, url: str) -> FakeResponse:
        self.urls.append(url)
        if self.fail:
            raise RuntimeError("connection reset")
        return FakeResponse(self.body)


def session_with_saved_text(file_ids: list[int]) -> MagicMock:
    session = MagicMock()
    session.scalars.return_value.all.return_value = file_ids
    return session


def executed_statements(session: MagicMock) -> list:
    return [c.args[0] for c in session.execute.call_args_list]


def test_upsert_document_keeps_saved_text_when_new_text_is_none():
    session = MagicMock()
    upsert_document(session, document(raw_text=None))
    statement = session.execute.call_args.args[0]
    assert "raw_text" not in conflict_set_clause(statement)


def test_upsert_document_overwrites_text_when_new_text_exists():
    session = MagicMock()
    upsert_document(session, document(raw_text="Minutes of the meeting"))
    statement = session.execute.call_args.args[0]
    assert "raw_text" in conflict_set_clause(statement)


def test_save_event_skips_download_for_files_with_saved_text():
    event = {
        **EVENT_JSON,
        "publishedFiles": [
            FILE_JSON,
            {**FILE_JSON, "id": 8185, "streamUrl": "https://cdn.example.com/new.pdf"},
        ],
    }
    request_ctx = FakeRequestContext(body=b"not a pdf")
    session = session_with_saved_text([8184])

    asyncio.run(save_event(session, request_ctx, event, "Planning Board", SCRAPED_AT))

    assert request_ctx.urls == ["https://cdn.example.com/new.pdf"]


def test_save_event_still_upserts_metadata_for_skipped_files():
    event = {**EVENT_JSON, "publishedFiles": [FILE_JSON]}
    session = session_with_saved_text([8184])

    asyncio.run(
        save_event(session, FakeRequestContext(), event, "Planning Board", SCRAPED_AT)
    )

    meeting_stmt, document_stmt = executed_statements(session)
    assert meeting_stmt.table.name == "planning_meetings"
    assert document_stmt.table.name == "planning_documents"
    assert "raw_text" not in conflict_set_clause(document_stmt)


def test_save_event_failed_download_does_not_wipe_saved_text():
    event = {**EVENT_JSON, "publishedFiles": [FILE_JSON]}
    session = session_with_saved_text([])

    asyncio.run(
        save_event(
            session, FakeRequestContext(fail=True), event, "Planning Board", SCRAPED_AT
        )
    )

    document_stmt = executed_statements(session)[-1]
    assert "raw_text" not in conflict_set_clause(document_stmt)
