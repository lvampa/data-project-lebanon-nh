# Raw source archive: requirements

**Status:** Draft
**Created:** 2026-11-06
**Updated:** 2026-11-13

## Introduction

The scrapers download police log PDFs and VGSI parcel pages, keep what they parse, and throw the original away.
When a parser is wrong, or a better one is written, the only way to redo the work is to download everything again, and some sources change or disappear.
There is also no record of exactly what the city published on a given day.

Success is that every police log PDF and every parcel page is kept as it was downloaded, in MongoDB, with when and where it came from.
Postgres holds every parsed, structured field; the archive holds raw, unparsed source, and nothing scraped is ever thrown away.
That includes each police log entry's raw text, the NH Secretary of State business pages behind the LLC table, the budget PDFs and their text, and a record of every AI call the police log normalization job makes.
The archive lets the operator rebuild Postgres records from stored originals without downloading anything, and shows what each source said on each date.
Writing to the archive never slows down or breaks the daily path that writes Postgres.

For police log PDFs the archive is the only copy of what the parser reads, because Postgres no longer stores the PDF text.
So police log reprocessing depends on it, and it is backed up.

The archive ships in two parts.
Writing ships between police log pipeline PR 1 and PR 2, and backups ship before police log pipeline PR 2b, which stops storing PDF text in Postgres.
Parcel replay and the check and versions commands ship with them.
CivicClerk agendas and minutes join the archive later, with their own scraper.

## Glossary

- **Archive:** The `raw_sources` collection in MongoDB.
- **Source:** One kind of archived original: `police_log_pdf`, `police_log_entry_text`, `vgsi_parcel`, `nh_sos_business`, or `budget_pdf`.
  `police_log_entry_text` holds one entry's raw text.
- **Source key:** What identifies one original within its source: the canonical URL for a log PDF, the parcel ID for a parcel page, the NH business ID for a business page, the source URL for a budget PDF, and the case number for an entry's raw text.
- **Raw field:** A value as the source gave it, before parsing: a PDF's bytes, a page's HTML, an entry's block of text, an unsplit reason and action line.
- **Structured field:** A value a parser extracted into its own column, such as a case number, an officer code, or a dispatch time.
- **Version:** One archived document: one distinct body for one source key.
- **Body:** The bytes as downloaded: the PDF file, or the parcel page's HTML.
- **Content hash:** The SHA-256 of the body, after removing the page-state fields of its source.
- **Page-state fields:** The ASP.NET hidden fields VGSI pages carry, `__VIEWSTATE`, `__VIEWSTATEGENERATOR`, and `__EVENTVALIDATION`, which can change without the parcel changing.
- **Replay:** Rebuilding Postgres records from archived bodies, with no download.
  For police log PDFs this is the police log pipeline's reprocess job.
- **AI call record:** One document in `ai_calls` for one call the police log normalization job made.
- **Backup:** A `mongodump` of the archive's database written outside the Docker volume.
- **Postgres path:** The spider callbacks and item pipelines that write to Postgres.

## Requirements

### Requirement 1: Keep every downloaded original

**User story:** As Connor, I want each police log PDF and parcel page kept exactly as it was downloaded, so that I can check any record against its source and redo the parsing later.

#### Acceptance criteria

1. WHEN the process job downloads a log PDF with status 200 and a body that starts as a PDF file, THE archive SHALL store its body, the URL it came from, the HTTP status, the content type, and the time it was fetched.
2. WHEN the VGSI spider downloads a parcel page with status 200, THE archive SHALL store its body with the same details.
3. THE archive SHALL record each version's source and source key.
4. THE archive SHALL record each version's content hash and its body size in bytes.
5. THE archive SHALL store bodies compressed.
6. IF a compressed body is larger than 15 MB, THEN THE archive SHALL store the version without its body, mark it as truncated, and log a warning.
7. THE archive SHALL NOT store responses with any status other than 200, VGSI street index pages, responses served from Scrapy's HTTP cache, or responses from any other spider.
8. THE archive SHALL store the body as the spider callback receives it, after HTTP decompression and redirects.
9. WHEN the LLC lookup loads an NH Secretary of State business page, THE archive SHALL store the page's HTML with the same details, keyed by the business ID, or by the searched name when the page has no ID.
10. WHEN the budget downloader fetches a budget PDF, THE archive SHALL store its bytes and the text extracted from it, keyed by the source URL.

### Requirement 2: Store each distinct version once

**User story:** As the operator, I want unchanged sources stored once, so that weekly scrapes of thousands of parcels do not fill the disk with copies.

#### Acceptance criteria

1. WHEN a downloaded body has the same content hash as a stored version of the same source key, THE archive SHALL update that version's last-seen time and seen count instead of storing a new version.
2. WHEN the content hash differs from every stored version of the source key, THE archive SHALL store a new version and keep the older ones.
3. THE content hash of a parcel page SHALL ignore its page-state fields, so that an unchanged parcel does not make a new version on each scrape.
4. THE archive SHALL NOT delete versions on its own.
5. WHEN the check command runs, THE check command SHALL report the archive's size and number of versions per source, and SHALL log a warning when the size passes 5 GB.

### Requirement 3: Never slow or break the Postgres path

**User story:** As the operator, I want a Mongo problem never to cost me Postgres data or a daily run, so that the archive cannot take the pipeline down.

#### Acceptance criteria

1. IF MongoDB is unreachable or an archive write fails, THEN THE spider SHALL store its Postgres records exactly as it would without the archive.
2. IF MongoDB cannot be reached within 2 seconds, or any archive operation takes longer than 5 seconds, THEN THE archive SHALL stop trying for the rest of the run and log one error, instead of waiting on each write.
3. THE archive SHALL write police log PDFs one at a time, before the spider's callback runs, and SHALL write other sources in batches of up to 50 and once more when the spider closes.
4. WHEN a spider closes, THE archive SHALL log how many versions it stored, how many it saw again, and how many it failed to write.
5. A failed archive write SHALL NOT change the exit status of the process job or the VGSI spider.
6. WHILE the archive is on, a process job run of 100 PDFs SHALL take no more than 10% longer than the same run with the archive off.
7. THE archive SHALL be turned on or off per spider by configuration, and SHALL be on by default for the process job and the VGSI spider.
8. WHEN the archive writes a police log PDF, THE archive SHALL tell the process job whether the write succeeded, so that the job can choose the error kind in police log pipeline criterion 2.8.

### Requirement 4: Use the archive

**User story:** As Connor, I want to rebuild records from stored originals and see which records have none, so that the archive earns its keep.

#### Acceptance criteria

1. THE archive SHALL let the police log reprocess job read the newest archived version of a log PDF by its canonical URL, and the exact version by its content hash.
2. WHEN the operator replays parcel pages, THE replay command SHALL parse the latest archived version of each parcel with the VGSI spider's parcel parser and store the result through its Postgres pipeline, without downloading anything.
3. THE replay command SHALL NOT write to the archive.
4. WHEN a replay finishes, THE replay command SHALL log how many parcels it replayed, how many records it inserted, updated, and left unchanged, and how many had no usable body.
5. THE check command SHALL report how many log PDFs that are `complete` or `error` in `pdf_urls` have an archived body, and SHALL list log PDFs with none, parcels in `properties` that have no archived version, and `ai` normalizations whose AI call record is missing.
6. THE operator SHALL be able to list every version of one source key, newest first, with its fetch time, content hash, size, and seen count.

### Requirement 5: Test against a real test database

**User story:** As Connor, I want archive tests to run against a real MongoDB that is never the live one, so that they prove the writes work and cannot touch real data.

#### Acceptance criteria

1. THE test suite SHALL run archive tests against a MongoDB database whose name ends in `_test`.
2. IF the configured MongoDB database name does not end in `_test`, THEN THE test suite SHALL stop before running any test.
3. THE test suite SHALL leave the test database empty after each test.
4. THE test suite SHALL cover a run with MongoDB unreachable, and SHALL show that the Postgres records are still stored.

### Requirement 6: Keep a record of every AI call

**User story:** As Connor, I want every AI call the normalization job makes kept with its prompt and raw answer, so that I can audit a value, compare AI answers with my corrections, and grow the evaluation set.

#### Acceptance criteria

1. THE archive SHALL store one AI call record per call, with the normalized field, the raw values sent, the prompt, the raw answer, the accepted items, the AI backend, the model, the prompt version, the duration, and the outcome.
2. THE archive SHALL store a record for failed calls as well as successful ones.
3. THE archive SHALL give each AI call record an ID that Postgres stores as the reference on each normalization the call produced.
4. THE archive SHALL let the operator list AI call records by field and prompt version, newest first.
5. AI call records SHALL follow requirement 3: a failed write never stops the normalization job from storing its results.

### Requirement 7: Back up the archive

**User story:** As Connor, I want the archive backed up, so that losing the Mongo volume does not lose the only copy of police log PDFs the city may have removed.

#### Acceptance criteria

1. WHEN the backup runs, THE backup job SHALL write a compressed `mongodump` of the archive's database to the backup folder, outside the Docker volume.
   The backup folder is `~/backups/data-project/mongo` on the host by default, and `MONGO_BACKUP_DIR` changes it.
   IF the backup folder does not exist or cannot be written, THEN THE backup job SHALL exit with an error that names the folder.
2. THE scheduler SHALL run the backup once a day.
3. THE backup job SHALL keep the 7 most recent daily backups and delete older ones.
4. IF the backup fails, THEN THE backup job SHALL exit with a non-zero status, so that the scheduler shows it failed.
5. THE operator SHALL be able to restore a backup into a MongoDB database whose name ends in `_test` with one command, to check that it is usable.

### Requirement 8: Keep every raw field, and every structured field in Postgres

**User story:** As Connor, I want nothing we scrape ever thrown away, with parsed fields in Postgres for reporting and raw source in MongoDB, so that every value can be traced to its source and reparsed.

#### Acceptance criteria

1. THE archive SHALL store every response the police log, VGSI, NH Secretary of State, and budget scrapers download with status 200, as requirement 1 describes for each source.
2. WHEN a police log PDF is ingested, THE archive SHALL store a `police_log_entry_text` version for each entry, keyed by case number, holding its raw text, its unsplit reason and action text, its source URL, and the parser version that cut it.
3. THE police log pipeline SHALL store every structured field the parser extracts in Postgres, including the officer code, every "Refer To" reference, and the parser version per entry.
4 to 8. Removed on 2026-11-13: there is no legacy data to copy. Nothing is live, so the databases are reset and rescraped.
9. THE archive SHALL record each version's fetch time, which replaces `log_entries.scraped_at`.
10. EXCEPT for police log entry texts, THE archive SHALL NOT store parsed or derived values.
    Entry texts are the one named exception: they are raw text, cut into entries by the parser, and each version records the parser version that cut it (8.2).
11. EXCEPT for planning document text, Postgres SHALL NOT store raw fields.
   Planning document text is the one named exception: admin search indexes it (search criterion 2.6), and it stays in Postgres until CivicClerk joins the archive under its own task.
12. Removed on 2026-11-13: the raw text columns are dropped by a plain migration, with no archive check.

## Out of scope

- CivicClerk agendas and minutes, and other sources.
  The document shape takes them without change; each joins when its scraper does.
- Raw geocoder responses.
  Connor chose not to keep them.
- Copying backups off the machine, such as to cloud storage.
  The backup folder can sit on an external drive; anything further is a later decision.
- Deleting or pruning versions.
  The check command warns at 5 GB; a pruning rule is a later decision.
  Backups are pruned to 7 days (7.3).
- Showing archived originals in the admin app or the API.
- File storage such as S3, and MongoDB GridFS.
- Removing the old `urls` collection.
