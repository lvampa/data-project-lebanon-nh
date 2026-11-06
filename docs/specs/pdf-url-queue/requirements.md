# PDF URL queue: requirements

**Status:** Done
**Created:** 2026-10-31
**Updated:** 2026-11-06

## Introduction

The police log scraper finds daily log PDFs, then downloads and parses them in a separate run.
The list of found PDFs and their processing state is a work queue.
It lives in a MongoDB `urls` collection.
The parsed entries go to Postgres, so the URL state change and the entry insert are two writes to two databases that cannot share a transaction.
Success is the queue living in a Postgres `pdf_urls` table, with entry inserts and URL completion committed together.
MongoDB stays in the stack for document-shaped work.

## Glossary

- **PDF URL:** One row in `pdf_urls`, keyed by its canonical URL.
- **Claim:** Moving a PDF URL from `pending` to `in_progress` so one spider run owns it.
- **Lease:** How long a claim stays valid, `CLAIM_LEASE` (2 hours).
- **Attempt limit:** `MAX_ATTEMPTS` (3), the number of claims after which an errored URL is no longer retried.

## Requirements

### Requirement 1: Record discovered PDF URLs

**User story:** As an operator, I want every linked log PDF recorded once, so that the processing run has a complete queue without duplicates.

#### Acceptance criteria

1. WHEN `build_daily_urls` finishes, THE `UrlRecordPipeline` SHALL insert every discovered PDF URL into `pdf_urls` with state `pending`.
2. IF a PDF URL with the same canonical URL already exists, THEN THE `UrlRecordPipeline` SHALL leave the existing row unchanged.
3. IF a spider run yields no URL records, THEN THE `UrlRecordPipeline` SHALL not open a database transaction.
4. THE `UrlRecordPipeline` SHALL validate each item with the `UrlRecord` model before writing it.

### Requirement 2: Claim pending URLs without overlap

**User story:** As an operator, I want concurrent processing runs to split the queue, so that no PDF is processed twice.

#### Acceptance criteria

1. WHEN `process_urls` starts, THE spider SHALL claim up to `limit` `pending` PDF URLs, oldest `created_at` first, in one statement.
2. THE claim statement SHALL skip rows locked by another transaction.
3. WHEN a PDF URL is claimed, THE spider SHALL set its state to `in_progress`, set `claimed_at` to the current UTC time, and add 1 to `attempts`.
4. IF no PDF URLs are pending, THEN THE spider SHALL issue no requests.

### Requirement 3: Requeue stale and failed URLs

**User story:** As an operator, I want crashed and failed runs retried a bounded number of times, so that transient failures heal and permanent ones stop.

#### Acceptance criteria

1. WHEN `process_urls` starts, THE spider SHALL set every `in_progress` PDF URL claimed more than `CLAIM_LEASE` ago to `error` with the message `Claim expired`.
2. WHEN `process_urls` starts, THE spider SHALL set every `error` PDF URL with fewer than `MAX_ATTEMPTS` attempts back to `pending`.
3. THE spider SHALL leave `error` PDF URLs with `MAX_ATTEMPTS` or more attempts in `error`.
4. THE spider SHALL run both requeue steps before claiming, so that a URL requeued in a run can be claimed in the same run.

### Requirement 4: Save a PDF's entries and its URL state together

**User story:** As an operator, I want a PDF marked `complete` only when its entries are saved, so that a crash cannot lose entries or leave them saved under an unfinished URL.

#### Acceptance criteria

1. WHEN the `PoliceLogPipeline` saves a PDF's entries, THE pipeline SHALL set the PDF URL to `complete` with `entry_count`, `raw_text` and `completed_at` in the same transaction as the entry inserts.
2. IF any entry insert fails, THEN THE `PoliceLogPipeline` SHALL roll back every entry from that PDF and set the PDF URL to `error` with the failure message.
3. THE `PoliceLogPipeline` SHALL keep entries from earlier PDFs in the same run committed when a later PDF fails.
4. IF a request, an archive fallback, or PDF parsing fails, THEN THE spider SHALL set the PDF URL to `error` with a message naming the step.
5. IF a PDF parses to zero entries, THEN THE spider SHALL set the PDF URL to `error` with `entry_count` 0 and the extracted `raw_text`.

### Requirement 5: Keep MongoDB for document-shaped work

**User story:** As Connor, I want MongoDB kept after the queue leaves it, so that document-shaped data has a home and I can practice with a document database.

#### Acceptance criteria

1. THE repository SHALL keep the `shared/mongo` package, the `mongo` compose service and the `pymongo` dependency.
2. THE police log queue SHALL NOT read or write MongoDB.
3. THE agent docs SHALL describe the Postgres queue in the data flow and key patterns.

## Out of scope

- Copying existing MongoDB `urls` documents into `pdf_urls`.
  The next `build_daily_urls` run rediscovers every PDF still linked from the index page.
- Changing how PDFs are parsed or how entries are deduplicated.
- An admin view of the queue.
