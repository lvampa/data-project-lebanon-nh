# Planning board: requirements

**Status:** Done
**Created:** 2026-06-03
**Updated:** 2026-10-16

## Introduction

Lebanon NH publishes Planning Board meetings, agendas, minutes, and attachments on its CivicClerk portal.
The portal has no export, and its public API rejects non-browser clients, so the records are hard to search or join with property data.
Success means every Planning Board meeting and its published documents are in PostgreSQL, with document text extracted, and refreshed daily without manual work.

## Glossary

- **CivicClerk:** The vendor portal at `lebanonh.portal.civicclerk.com` that hosts city meeting records, backed by an OData v4 API at `lebanonh.api.civicclerk.com/v1`.
- **Event:** One CivicClerk meeting record, identified by a CivicClerk event id.
- **Event category:** A CivicClerk grouping of events, such as Planning Board, referenced by `eventGroupId`.
- **Published file:** A document attached to an event, such as an agenda, minutes, or attachment, identified by a CivicClerk file id.
- **WAF:** The web application firewall in front of the API, which returns 404 to plain HTTP clients.

## Requirements

### Requirement 1: Find the Planning Board category

**User story:** As an operator, I want the scraper to find the Planning Board category on its own, so that a changed category id does not break the job.

#### Acceptance criteria

1. WHEN the scraper starts, THE scraper SHALL fetch the list of event categories from the CivicClerk API.
2. THE scraper SHALL select the first category whose name contains "planning", compared case-insensitively.
3. IF no category name contains "planning", THEN THE scraper SHALL fail with an error that lists the category names it received.
4. THE scraper SHALL send all API requests through a browser request context that has first loaded the portal home page, so the WAF does not block them.

### Requirement 2: Fetch Planning Board meetings

**User story:** As an analyst, I want every Planning Board meeting recorded, so that I can see the full history of board activity.

#### Acceptance criteria

1. WHEN the category is found, THE scraper SHALL fetch events in that category in pages of 100, newest first, with published files included.
2. THE scraper SHALL keep requesting pages until a page returns fewer than 100 events or no events.
3. WHERE a `--limit` greater than 0 is given, THE scraper SHALL process at most that many events, taken from the newest.
4. IF the category has no events, THEN THE scraper SHALL finish without writing any rows and without error.

### Requirement 3: Store meeting records

**User story:** As an analyst, I want each meeting stored with its date, title, location, and status, so that I can filter and link meetings.

#### Acceptance criteria

1. THE scraper SHALL store each event as one meeting row with the CivicClerk event id, title, category name, meeting date, location, status, portal URL, and scrape time.
2. THE scraper SHALL set the portal URL to `https://lebanonh.portal.civicclerk.com/event/<event id>`.
3. IF an event's start date is missing or cannot be parsed as ISO 8601, THEN THE scraper SHALL store the meeting with a null meeting date.
4. IF an event has no status object, THEN THE scraper SHALL store the meeting with a null status.
5. IF a meeting with the same CivicClerk event id already exists, THEN THE scraper SHALL update its fields instead of adding a duplicate.

### Requirement 4: Store meeting documents and their text

**User story:** As an analyst, I want agenda, minutes, and attachment text stored, so that I can search what the board discussed.

#### Acceptance criteria

1. THE scraper SHALL store each published file of an event as one document row with the CivicClerk file id, event id, file name, file type, download URL, extracted text, and scrape time.
2. THE scraper SHALL map file type 1 to "Agenda", 2 to "Minutes", and 3 to "Attachment".
3. IF a file type is not 1, 2, or 3, THEN THE scraper SHALL store the number as text.
4. WHERE a file has a `streamUrl`, THE scraper SHALL use it as the download URL.
5. IF a file has no `streamUrl`, THEN THE scraper SHALL build the download URL from the `GetEventFileStream` endpoint with the file id and type.
6. WHEN a downloaded file starts with the `%PDF` signature, THE scraper SHALL store the text of all its pages, joined by newlines.
7. IF a downloaded file is empty, is not a PDF, or cannot be parsed, THEN THE scraper SHALL store the document with null text.
8. IF a file download raises an error, THEN THE scraper SHALL log a warning with the file id and store the document with null text.
9. IF a document with the same CivicClerk file id already exists, THEN THE scraper SHALL update its fields instead of adding a duplicate.
10. IF an event has no published files, THEN THE scraper SHALL store the meeting and no documents.

### Requirement 5: Run daily

**User story:** As an operator, I want the scrape to run on a schedule, so that new meetings appear without manual runs.

#### Acceptance criteria

1. THE Airflow DAG `civicclerk_planning` SHALL run the scraper every day at 05:00 UTC.
2. THE DAG SHALL not backfill runs for dates before it was deployed.
3. IF a run fails, THEN THE DAG SHALL retry it once after 5 minutes.
4. IF any database write in a run fails, THEN THE scraper SHALL roll back all writes from that run and exit with an error.

## Out of scope

- Other CivicClerk boards, such as City Council or Zoning Board. Only the first "planning" category is scraped.
- Storing the original file bytes. Only the extracted text is kept.
- OCR for scanned PDFs. Pages with no text layer yield empty text.
- Text from non-PDF files, such as Word documents.
- Removing meetings or documents that CivicClerk later deletes.
- Linking meetings to properties. The search sync resolves meeting locations to addresses separately.
