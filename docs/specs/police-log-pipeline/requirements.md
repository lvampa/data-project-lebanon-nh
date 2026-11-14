# Police log pipeline: requirements

**Status:** In progress
**Created:** 2026-11-06
**Updated:** 2026-11-13

## Introduction

The city posts one police log PDF per day.
The pipeline finds the PDFs, parses them into `log_entries`, and feeds two consumers: the admin API and admin search that Connor uses, and the static JSON that the public site and map read.

Today the flow stops early.
Postgres holds 343 entries from 3 PDFs, 650 PDFs are waiting, and 10 are stuck mid-claim.
No incident type or address has ever been normalized, so the public map is empty and search cannot group "MV Complaint" with other traffic calls.
A parser fix cannot repair rows already stored, because nothing can reprocess them.

Success is that a new PDF flows from the city page to admin search and to the public JSON on a daily schedule, with every value the PDF gave kept as it was and a normalized value stored beside it.
The one manual step is the AI normalizing: Connor runs one command on his Mac, and the daily run picks up whatever is normalized so far.
AI does the normalizing, either through `claude -p` on Connor's Max plan or through a free local model, and never through a paid API.
Connor can correct any normalized value, and his correction always wins.
When AI or the geocoder fails, the pipeline keeps going on raw values and tries again later.
The public site gets a filtered subset of the same data the admin sees, not a separate pipeline.

AI is used only where the values are open-ended.

| Value | Produced by | Why |
|---|---|---|
| Category and plain type name | AI | Incident types are an open vocabulary: 92 distinct values in 3 days, and growing. |
| Normalized address and location kind | Rules first, then AI for the rest | Locations are free text, such as "HANNAFORD'S MARKET - MARKET ST". A house number on a known street needs no AI. |
| Coordinates | Geocoder | A lookup, checked against the city bounds. |
| Disposition, call source, officer, times | Parser rules | Closed sets or fixed formats that a rule reads exactly. |

This spec builds on the `fix/integration` and `fix/url-queue` branches, which already complete a PDF in the same commit as its entries, retry failed claims, and keep the URL queue in Postgres.
Postgres holds every parsed, structured field.
The MongoDB raw source archive, under its own spec, holds only raw, unparsed source: the original log PDFs, each entry's raw text, and a record of every AI call.
Nothing raw is ever discarded.
Reprocessing reads the archived PDFs, so the archive's write half ships before the ingest changes here.
The work ships as a series of pull requests, each useful on its own; tasks.md lists them.

## Glossary

- **Log PDF:** One daily police log PDF from the city's Daily Police Log page.
- **URL record:** The row in the Postgres `pdf_urls` table that tracks one log PDF and its state: `pending`, `in_progress`, `complete`, or `error`.
- **Entry:** One row in `log_entries`, parsed from one block of a log PDF and keyed by case number.
- **Raw value:** A field value as the parser read it from the PDF, such as `BUSINESS CHECK - OPEN` or `HANNAFORD'S MARKET - MARKET ST`.
- **Normalized value:** A cleaned value derived from a raw value, such as a category, a standard address, or coordinates.
- **Normalized field:** One of the two fields that get normalized values: incident type and location.
- **Normalization:** The stored normalized value for one distinct raw value of a normalized field.
- **Source:** Who produced a normalization: `rule`, `ai`, or `human`.
  `rule` means the rule pass settled it with no AI call.
  A location has one source for the whole record; how its coordinates were found (geocoder, place code, or by hand) is recorded separately.
- **Review mark:** A flag on a normalization or a raw value that asks Connor to look at it.
- **Normalization job:** The scheduled job that finds raw values without a normalization and creates one.
- **AI backend:** What answers an AI call: `claude -p` on the Max plan, or a local model.
- **AI call:** One request the normalization job sends to the AI backend.
- **Canonical address rules:** Fixed text rules that make letter case, spacing, punctuation, and street suffix and direction spellings (such as `STREET` and `ST`) produce one form.
- **Rule pass:** The step of the normalization job that settles locations with the canonical address rules, the street list, and known place codes, before any AI call.
- **Street list:** The distinct street names in the parcel locations, in canonical form.
- **Prompt version:** The version of a prompt's text. For locations it also names the version of the street list the prompt carried.
- **Geocoder:** Nominatim, the service the admin API already uses to turn an address into coordinates.
- **Header-like line:** A line in a log PDF's text that starts with a case number pattern, such as `26-13339`.
- **Place code:** The bracketed code the PDF prints before some locations, such as `[L HANNAF]`.
- **Category:** One of Fire, EMS, Police, Traffic, Administrative.
- **Archive:** The MongoDB raw source archive in `docs/specs/raw-source-archive/`, which keeps each downloaded log PDF's original bytes, each entry's raw text, and each AI call.
- **Content hash:** The SHA-256 of a log PDF's bytes, which names one archived version.
- **Reprocess:** Extracting text again from a log PDF's archived original and updating its entries, without downloading the PDF again.
- **City bounds:** A fixed box around Lebanon, NH.
- **Placed:** A location that has coordinates.
- **Incident:** An entry whose `parse_error` is not set.
- **Consumer models:** The tables or views that dbt builds from entries and normalizations, which the admin API, admin search, and the public export read.
- **Evaluation set:** A file in the repo of raw incident types and raw locations, each with the normalized value a person decided is right.
- **Public export:** The JSON files `report-gen` writes to `frontend/web/public/data`.
- **Public window:** The most recent 90 days of incidents, counted back from the newest log date stored.
- **Block level:** A house address with its number rounded down to the hundred, such as "100 block of Hanover St", and coordinates rounded to 3 decimal places, about 100 meters.

## Requirements

### Requirement 1: Keep every raw value

**User story:** As Connor, I want the original value from the PDF kept next to each normalized value, so that I can always check a record against its source and redo the normalizing.

#### Acceptance criteria

1. THE pipeline SHALL store each entry's raw incident type, location, officer, disposition, and call source as parsed from the log PDF.
2. THE normalization job SHALL NOT change or delete any raw value.
3. THE parser SHALL store the place code and the officer code the PDF prints, instead of discarding them.
4. THE archive SHALL keep the original bytes of each log PDF, and THE pipeline SHALL record on its URL record the content hash of the version it ingested.
   Postgres stores neither the PDF nor its extracted text.
   The archive also keeps each entry's raw text and unsplit reason and action text, keyed by case number (archive requirement 8).
5. THE pipeline SHALL record on each entry the log date of its PDF, next to the source URL it already stores.
6. THE pipeline SHALL record on each entry when it was first stored, when its parsed values last changed, and the parser version that produced it.
7. THE pipeline SHALL record on each URL record the parser version and the PDF text extractor version that produced its entries.

### Requirement 2: Ingest every log PDF once and recover from failures

**User story:** As the operator, I want each log PDF processed exactly once and failed downloads retried, so that the backlog clears and nothing gets stuck.

#### Acceptance criteria

1. THE `pdf_urls` table SHALL hold at most one URL record per canonical URL, even when two discovery runs overlap.
2. THE process job SHALL store a log PDF's entries and mark its URL record `complete` in one transaction.
3. IF that transaction fails, THEN THE process job SHALL mark the URL record `error` with the reason and SHALL leave none of that PDF's entries from this run in Postgres.
4. IF one entry of a log PDF fails validation, THEN THE process job SHALL skip that entry, store the PDF's other entries, and count the skipped entry on the URL record.
5. THE process job SHALL skip an entry with no case number in the same way.
6. A failure in one log PDF SHALL NOT lose entries of other PDFs in the same run.
7. IF a download fails or times out, THEN THE process job SHALL mark the URL record `error` with the reason and SHALL try it again on later runs until it has had 3 attempts.
8. IF a log PDF downloads but yields no entries or fails to save, THEN THE process job SHALL mark the URL record `error`, and SHALL NOT download it again while the archive holds its original.
   IF the archive did not store that PDF's original, THEN THE process job SHALL mark it as a download error, so that it is downloaded and archived again.
9. WHEN a URL record has been `in_progress` for more than 120 minutes, THE process job SHALL return it to `pending` and count that as an attempt.
10. WHEN a URL record reaches 3 attempts without completing, THE process job SHALL leave it in `error` until the operator resets it.
11. THE operator SHALL be able to list URL records in `error` with their reasons and reset chosen ones to `pending` with one command.
12. WHEN the same case number appears in two log PDFs, THE pipeline SHALL keep the values from the PDF with the later log date.
13. WHEN a log PDF is processed, THE process job SHALL record on the URL record how many entries it parsed, stored, and skipped.
14. IF the number of header-like lines in a log PDF's text differs from the number of entries parsed, THEN THE process job SHALL record both numbers on the URL record and log a warning.
15. IF any URL record moves to `error` during a run, THEN THE process job SHALL exit with a non-zero status after finishing the other records.

### Requirement 3: Parse what the PDF contains

**User story:** As Connor, I want the parser to capture what it drops or garbles today, so that fewer entries have missing locations, glued-on dispositions, and lost references.

#### Acceptance criteria

1. WHEN an entry gives its location on a "Vicinity of:" line, THE parser SHALL store that location.
2. WHEN an entry has a "Call Source:" line, THE parser SHALL store that value as the call source.
3. WHEN the PDF text extractor changes version, THE pipeline SHALL treat it as a parser change: the parser version is bumped and the archived PDFs are reprocessed.
4. THE parser SHALL split the header's reason and action text into a raw incident type and a raw disposition using a disposition list held in the repo.
5. THE disposition list SHALL include every disposition found in the stored PDFs, including Investigated, Summons Issued, Removed Hazard, Transported/Relayed, Paperwork Served, and Paperwork NOT Served.
6. IF no disposition in the list matches an entry, THEN THE parser SHALL store the unsplit text as the raw incident type, leave the disposition empty, and mark the entry as having an unmatched disposition.
7. THE operator SHALL be able to list the entries marked as having an unmatched disposition.
8. THE parser SHALL store every "Refer To" reference an entry prints, of any kind, including Citation and Accident.

### Requirement 4: Reprocess stored PDFs

**User story:** As the operator, I want to reparse PDFs already downloaded after a parser fix, so that old entries get the fix without downloading anything again.

#### Acceptance criteria

1. WHEN the operator runs a reprocess for a date range or for all dates, THE reprocess job SHALL extract text again from the newest archived version of each matching URL record that is `complete` or `error`, and parse it.
2. THE reprocess job SHALL work through URL records in log date order.
3. THE reprocess job SHALL update the parsed values of each existing entry by case number, and SHALL insert entries that did not exist.
4. WHEN a reprocess of an `error` URL record stores at least 1 entry, THE reprocess job SHALL mark the URL record `complete`.
5. THE reprocess job SHALL NOT download any PDF.
6. THE reprocess job SHALL NOT change or delete any normalization.
7. IF an entry stored from a log PDF is no longer found when that PDF is reprocessed, THEN THE reprocess job SHALL keep the entry, mark it as not found in the latest parse, and count it in its log.
8. WHEN a reprocess produces a raw value that has no normalization, THE normalization job SHALL pick it up on its next run.
9. WHEN the same reprocess runs twice with the same parser version, THE second run SHALL change no entry, including its last-changed time.
10. WHEN the reprocess finishes, THE reprocess job SHALL log how many entries it updated, inserted, left unchanged, and marked as not found.
11. WHILE the process job is running, THE reprocess job SHALL NOT start, and the reverse.
12. IF a matching URL record has no archived version, THEN THE reprocess job SHALL return it to `pending`, so that it is downloaded and archived again, and count it in its log.
13. IF the archive is unreachable, THEN THE reprocess job SHALL exit with an error before changing any entry.

### Requirement 5: Normalize incident types

**User story:** As a public visitor, I want incidents grouped into a few plain categories with readable names, so that I can filter the map and list without learning dispatch codes.

#### Acceptance criteria

1. THE normalization job SHALL give each distinct raw incident type one normalization with a category and a normalized type name.
2. THE normalization job SHALL accept only the five categories: Fire, EMS, Police, Traffic, Administrative.
3. THE normalization job SHALL treat raw incident types that differ only in letter case or spacing as one value, and SHALL send it once.
4. THE normalization job SHALL send each distinct raw incident type to AI at most once, unless the operator asks for it to be redone.
5. THE normalization job SHALL send the normalized type names already in use with each AI call, so that AI can reuse a name instead of inventing a near copy.
6. IF AI returns a normalized type name that differs from one already in use only in letter case or spacing, THEN THE normalization job SHALL store the name already in use.
7. IF a normalized type name contains, as a whole word, an abbreviation on the dispatch abbreviation list held in the repo, such as MV, BOL, or ATL, THEN THE normalization job SHALL discard that item.

### Requirement 6: Normalize locations and place them on the map

**User story:** As a public visitor, I want incidents shown at the right spot on the map, so that I can see what happened near me.

#### Acceptance criteria

1. THE normalization job SHALL give each distinct raw location one normalization with a normalized address and a location kind: `address`, `intersection`, `place`, or `highway`.
2. WHEN a raw location's place code already has coordinates stored, THE normalization job SHALL reuse them instead of asking the geocoder.
3. WHEN a location has a normalized address and is not placed, THE normalization job SHALL ask the geocoder for coordinates.
   IF the location's kind is `highway` and it names no cross street, exit, or landmark, THEN THE normalization job SHALL NOT geocode it and SHALL give it a review mark.
4. IF the geocoder returns coordinates outside the city bounds, THEN THE normalization job SHALL discard them and leave the location not placed.
5. IF the geocoder returns no result or fails, THEN THE normalization job SHALL keep the normalized address and leave any existing coordinates unchanged.
6. THE normalization job SHALL ask the geocoder about one location at most 3 times, and SHALL then give the location a review mark.
7. THE normalization job SHALL send the geocoder at most 1 request per second.
8. THE normalization job SHALL send the geocoder at most 600 requests per run, and SHALL leave the rest for the next run.
9. THE normalization job SHALL record with each set of coordinates whether they are `exact`, for a matched address, place, or intersection, or `approximate`, for a street or highway matched without a point on it.
10. THE normalization job SHALL NOT change a location normalization whose source is `human`, including its coordinates.
11. THE consumer models SHALL work out each location's public location and public coordinates as in 11.6 and 11.7, in one place, so that every consumer reads the same values.
12. WHEN Connor saves a normalized address in the admin and geocoding fails, THE admin API SHALL keep the coordinates the location already had.
13. THE normalization job SHALL send each distinct raw location to AI at most once, unless the operator asks for it to be redone.
14. THE normalization job SHALL apply the canonical address rules to every waiting raw location before making any AI call, and SHALL treat raw locations with the same canonical form as one value.
15. WHEN a raw location's canonical form is a house number followed by a street on the street list, THE normalization job SHALL store it as kind `address` with source `rule`, and SHALL NOT send it to AI.
16. WHEN a raw location's canonical form is two streets on the street list joined by `and`, `&`, or `/`, THE normalization job SHALL store it as kind `intersection` with source `rule`, and SHALL NOT send it to AI.
17. WHEN a raw location's place code already has a normalization of kind `place` with no review mark, THE normalization job SHALL copy its normalized address and kind with source `rule`, and SHALL NOT send it to AI.
18. THE normalization job SHALL send to AI only the raw locations that 6.15 to 6.17 did not settle.
19. THE canonical address rules SHALL be deterministic, SHALL make no network or database call, and SHALL have one implementation that the normalization job and any other consumer share.
20. THE normalization job SHALL build the street list at the start of each run from the parcel locations, with house numbers and units removed and the canonical address rules applied.
21. THE normalization job SHALL send the street list with every location AI call.
22. IF an AI answer gives a street that is not on the street list, THEN THE normalization job SHALL store the item with a review mark.
23. IF the street list is empty, THEN THE normalization job SHALL make no location AI calls in that run and SHALL log an error.
24. THE normalization job SHALL record, with each location AI call and each normalization it stores from one, a prompt version that changes whenever the street list changes.

### Requirement 7: Record where each normalization came from and let Connor correct it

**User story:** As Connor, I want to see whether AI or I set each normalized value and to fix the wrong ones, so that my corrections stick.

#### Acceptance criteria

1. THE pipeline SHALL record for each normalization its source, when it was created, and when it was last updated.
2. WHEN the source is `ai`, THE pipeline SHALL also record a reference to the AI call that produced it, whose archive record holds the AI backend, the model, and the prompt version.
3. THE admin API SHALL list the normalizations of each normalized field with the raw value, the normalized value, the source, the review mark, and the number of entries that use the raw value.
4. THE admin API SHALL filter that list by source, by review mark, and by whether a normalization exists yet.
5. THE admin API SHALL let Connor set or change the normalized value of any raw value in either normalized field, including one that has no normalization yet.
6. WHEN Connor saves a normalization, THE admin API SHALL set its source to `human` and clear its review mark.
7. IF Connor saves an incident type category outside the five, THEN THE admin API SHALL reject the change with status 422.
8. THE admin API SHALL accept coordinates from Connor that fall outside the city bounds, so that he can place a call the police answered in a neighboring town.
9. No job or script SHALL overwrite a normalization whose source is `human`.
10. THE normalization job SHALL be the only job that writes `ai` normalizations.
    The two existing categorizer scripts go away.
11. WHEN the operator asks to redo the `ai` normalizations for one normalized field, THE normalization job SHALL keep each old value until a valid new one replaces it, and SHALL leave `human` ones unchanged.
12. WHEN Connor asks to hand a `human` normalization back to AI, THE admin API SHALL delete it and its failed attempt count, so that the normalization job treats the raw value as new.
13. WHEN Connor replaces an `ai` normalization, THE AI's answer SHALL stay in the archive's record of that AI call, so that AI answers can be compared with his corrections.
    WHILE MongoDB is down, an AI call's record can be missing; the normalization is stored anyway.
14. WHEN the operator asks for a redo, THE normalization job SHALL NOT send a raw value whose normalization already has the current prompt version.

### Requirement 8: Survive AI failures

**User story:** As the operator, I want a failed or empty AI answer to cost nothing but a delay, so that one bad call never corrupts data or stops the pipeline.

#### Acceptance criteria

1. IF an AI call exits with an error or runs longer than 5 minutes, THEN THE normalization job SHALL store nothing from that call and leave its raw values waiting for the next run.
2. IF an AI call returns an empty answer or an answer that does not match the required schema, THEN THE normalization job SHALL store nothing from that call.
3. IF an AI answer leaves out some of the raw values it was sent, THEN THE normalization job SHALL store the valid items and leave the missing ones waiting.
4. IF an AI answer includes a raw value that was not sent, a raw value more than once, or a category outside the five, THEN THE normalization job SHALL discard those items.
5. THE AI answer SHALL say for each item whether AI is unsure, and THE normalization job SHALL store an unsure item with a review mark.
6. THE normalization job SHALL count a failed attempt against a raw value only when its own item was missing or discarded, not when the whole call failed.
7. WHEN a raw value reaches 3 failed attempts, THE normalization job SHALL stop sending it and give it a review mark.
8. IF one AI call fails for a reason other than login or a usage limit, THEN THE normalization job SHALL continue with the remaining batches and the other normalized field.
9. IF an AI call fails because the AI backend is not logged in or has hit a usage limit, THEN THE normalization job SHALL stop making AI calls for that run.
10. WHEN the normalization job finishes, THE job SHALL log for each normalized field how many values it normalized, how many items it discarded, and how many values still wait.
11. IF every AI call in a run fails, THEN THE normalization job SHALL exit with a non-zero status.
12. WHILE a raw value has no normalization, THE admin API and admin search SHALL show the entry with its raw value and empty normalized fields.
13. THE normalization job SHALL record every AI call in the archive, including failed ones, with its prompt, raw answer, AI backend, model, prompt version, duration, and outcome.
14. IF the archive cannot be written, THEN THE normalization job SHALL still store valid normalizations and SHALL log how many call records were lost.

### Requirement 9: Run AI without a paid API

**User story:** As Connor, I want AI steps to run on my Max plan or a free local model, so that normalizing costs nothing extra.

#### Acceptance criteria

1. THE normalization job SHALL send AI calls to the AI backend named in configuration: `claude -p` with the subscription login of the person running the job on Connor's Mac and a small model by default, or a local model when Connor turns it on.
2. IF the AI backend is `claude -p` and `ANTHROPIC_API_KEY` is set, THEN THE normalization job SHALL exit with an error before making any AI call, because the CLI bills the key when it is present.
3. THE test suite SHALL run one set of contract tests against every AI backend, covering a valid answer, an empty answer, a malformed answer, a timeout, and a login failure.
4. THE normalization job SHALL take the model name from configuration and record it as in 7.2.
5. THE normalization job SHALL send distinct raw values, not entries, with at most 50 values per AI call.
6. THE normalization job SHALL make at most 10 AI calls per run, 5 for each normalized field with unused calls passing to the other, and SHALL leave the rest for the next run.
7. IF the configured AI backend is missing, not logged in, or not reachable, THEN THE normalization job SHALL exit with an error that says so before sending any raw value.
8. THE AI backend SHALL make each AI call with every tool turned off, from an empty working directory created for that call, and without loading project or user settings, hooks, or MCP servers.
9. THE AI backend SHALL receive only the prompt and the answer schema and SHALL return only the answer, and THE normalization job SHALL be the only code that reads raw values from or writes normalizations to the database.

### Requirement 10: Search and filter normalized records in the admin

**User story:** As Connor, I want to search and filter incidents by normalized values, so that one query finds every matching record however the PDF spelled it.

#### Acceptance criteria

1. THE incidents API SHALL return each incident with both the raw and the normalized value of each normalized field, plus coordinates when the location is placed.
2. THE incidents API SHALL filter by category, normalized type name, and normalized address.
3. THE admin search SHALL query the consumer models in Postgres, with no separate search index.
4. THE admin search SHALL match a query against the case number, the raw and normalized incident type, the category, the raw and normalized location, the disposition, and the officer of each incident.
   Officer names are searchable in the admin only, and the public export never shows them (11.4).
5. WHEN a query has more than one word, THE admin search SHALL return only incidents that match every word.
6. WHEN a query word of 5 or more letters has one letter missing, extra, or wrong compared with a stored word, such as "Hanovr" for "Hanover", THE admin search SHALL still match it.
7. WHEN a query word of at least 4 digits and hyphens is part of a case number, such as "13339" for "26-13339", THE admin search SHALL return the incident with that case number.
8. WHEN Connor searches for a normalized address, THE admin search SHALL return incidents at that address whatever raw spelling each entry used.
9. THE admin search SHALL order results by how well they match, then by reported time, newest first.
10. WHEN a normalization changes, THE admin search SHALL reflect it on the next request, with no sync, build, or reprocess.
11. WHILE the database holds 100,000 incidents, THE admin search SHALL answer a query of up to five words within 1 second.
12. THE stats API SHALL count incidents by category and by normalized type name.
13. THE incidents API, the admin search, and the public export SHALL all leave out entries with `parse_error` set, so that the three agree on what an incident is.

### Requirement 11: Publish a subset for the public list and map

**User story:** As a public visitor, I want the list and map to show recent incidents with clean types and real locations, so that I can filter by kind of incident and date.

#### Acceptance criteria

1. THE public export SHALL read the same normalized incident data as the admin API, with a filter on top, and SHALL NOT run its own parsing or normalizing.
2. THE public export SHALL include only incidents inside the public window, and SHALL NOT cap them at a fixed row count.
3. THE public export SHALL write for each incident: case number, reported date and time, category, normalized type name, raw incident type, disposition, call source, public location, public coordinates, whether the coordinates are exact or approximate, and the source PDF address.
4. THE public export SHALL NOT write officer names, officer codes, reference numbers, response times, or anything about where a normalization came from.
5. THE public export SHALL keep every field name it writes today, with an empty value for the fields in 11.4, so that the current site keeps working.
6. WHEN a location's kind is `address`, THE public location and public coordinates SHALL be at block level, and a house number under 100 SHALL be written as the street name alone.
7. WHEN a location's kind is `intersection`, `place`, or `highway`, THE public location and public coordinates SHALL be the normalized address and coordinates as stored.
8. IF an incident's location is not placed, THEN THE public export SHALL write the incident with empty coordinates.
9. IF an incident's location has no normalization yet, THEN THE public export SHALL write an empty public location, because the raw location may be a house address.
10. IF an incident's type has no normalization yet, THEN THE public export SHALL write the raw incident type with an empty category and normalized type name.
11. THE public export SHALL count incidents in `stats.json` by category, by normalized type name, and by weekday, over the public window only.
12. THE public export SHALL keep writing `addresses.json` in its current shape, from the incidents and public locations in the public window.

### Requirement 12: Run the stages in order on a schedule

**User story:** As the operator, I want the stages scheduled and chained, so that new logs reach admin search without me starting anything.

#### Acceptance criteria

1. THE scheduler SHALL run discovery once a day.
2. WHEN discovery finishes, THE scheduler SHALL run processing, then geocoding, then the consumer model build, in that order.
   The scheduler does not run normalization; geocoding and the build work on whatever has been normalized so far (requirement 16).
3. THE process job SHALL handle up to 100 URL records per run.
4. THE scheduler SHALL allow at most one run of each police log job at a time, counting reprocess.
5. THE scheduler SHALL stop any police log task that runs longer than 60 minutes and mark it failed.
6. IF the processing or geocoding stage fails, THEN THE scheduler SHALL still run the stages after it.
7. WHEN a stage fails after its retries, THE scheduler SHALL show the run as failed and log the stage name and reason.
8. THE README SHALL document the one command that applies the database migrations, and THE operator SHALL run it by hand before any police log job runs. Nothing applies them at startup.
9. THE scheduler SHALL NOT run the public export or deploy the site.
   The public export is written from the consumer models when `deploy.sh` runs, and the files are not committed.

### Requirement 13: Test against a real database without touching live data

**User story:** As Connor, I want pipeline tests to run against a real test database and never the live one, so that tests prove the writes work and cannot damage real records.

#### Acceptance criteria

1. THE test suite SHALL run pipeline, reprocess, normalization, and API tests against a Postgres database whose name ends in `_test`, with its schema built by running the migrations.
2. IF the configured Postgres database name does not end in `_test`, THEN THE test suite SHALL stop before running any test.
3. THE test suite SHALL leave the test database empty of test rows after each test.
4. THE test suite SHALL run the migrations up to head and back down on an empty database.
5. THE test suite SHALL use a fake AI backend and a fake geocoder, and SHALL make no real AI call and no request to Nominatim.
6. THE test suite SHALL cover: the same case number stored twice gives one row, a bad entry does not lose earlier entries, a URL record is not `complete` before its entries are committed, the later log date wins when the older PDF is processed second, and two claims of the same URL record give one winner.

### Requirement 14: Check the data before consumers read it

**User story:** As Connor, I want bad data caught by a failing check, not by a resident looking at the map, so that mistakes stop before they are published.

#### Acceptance criteria

1. WHEN the consumer models are built, THE build SHALL run data checks and SHALL fail if any check fails.
2. THE data checks SHALL fail if a location has coordinates outside the city bounds that were not set by hand.
3. THE data checks SHALL fail if a raw incident type ends with a value from the disposition list.
4. THE data checks SHALL fail if a category is outside the five, or a case number appears more than once among incidents.
5. THE data checks SHALL fail if the public set holds an incident outside the public window, an officer name, or a house address that is not at block level.
6. WHEN a data check fails, THE build SHALL name the check and the number of rows that failed it.

### Requirement 15: Measure how well AI normalizes

**User story:** As Connor, I want a score for each prompt, model, and backend, so that I can choose between them with a number and show how the AI stage is checked.

#### Acceptance criteria

1. THE repo SHALL hold an evaluation set of at least 50 raw incident types and at least 50 raw locations, taken from real log PDFs.
2. THE evaluation command SHALL run a named AI backend, model, and prompt version against the evaluation set, and SHALL neither read nor write the database, so that the same inputs give comparable scores.
3. THE evaluation command SHALL report for incident types the share with the right category, and for locations the share with the right kind and the share with the right normalized address.
4. THE evaluation command SHALL report how many items the answer checks discarded and how many were marked unsure.
5. THE evaluation command SHALL list each wrong item with the raw value, the expected value, and the AI's value.
6. THE evaluation command SHALL compare normalized addresses and type names without regard to letter case or spacing.
7. THE evaluation SHALL NOT run in the test suite or the pre-push hook, because it makes real AI calls.
8. THE local model backend SHALL pass the same contract tests as `claude -p`, and its evaluation score SHALL be recorded in the repo before it is used for a scheduled run.

### Requirement 16: Run AI normalization by hand on Connor's Mac

**User story:** As Connor, I want to run the AI normalizing myself from my Mac with my normal Claude login, so that no long-lived token sits in `.env` and no container holds a Claude login.

#### Acceptance criteria

1. THE normalization job SHALL run as one documented command from the repo root on Connor's Mac, with his own `claude` login and no Claude token in `.env`.
2. WHILE the process, reprocess, or geocode job is running, THE normalization job SHALL exit with a non-zero status and say another police log job is running.
3. WHILE the normalization job is running, THE process, reprocess, and geocode jobs SHALL NOT start.
4. THE normalization job SHALL exit with a non-zero status when it cannot run or every AI call fails, and with zero otherwise.
5. THE daily schedule SHALL NOT run the normalization job.

## Out of scope

- Changes to the public site or admin pages.
  This feature changes the data and API they read.
  The admin screens for reviewing and correcting normalizations are a follow-up Connor will build with the team.
- Normalizing officers, dispositions, and call sources.
  Linking officers to the roster belongs with people pages.
  Dispositions and call sources come from short fixed lists, which the parser handles in requirement 3.
- Parsing every unit's timestamps on multi-unit calls.
- Removing or renaming fields in the public export.
- Running the public export on a schedule, or deploying the site automatically.
  The export runs as part of the manual deploy, so a scheduled export would have no reader.
- Paid accounts that see the full data.
  Requirement 11.1 keeps the door open: the public export is a filter over the full data.
- Public pages about officers.
- Hiding what the city already publishes.
  The export leaves out officer names but links to the source PDF, which prints them.
  The filter is about what this site gathers and makes searchable, not secrecy.
- Asking AI to split reason and action text the parser could not split.
  Dispositions are a closed list, so the fix is to add the missing value to the list and reprocess.
  AI suggesting additions to that list is a possible follow-up.
- Adding Connor's corrections to the evaluation set automatically.
  7.13 keeps the data; turning it into labeled items is a follow-up.
- How the archive stores and backs up its documents.
  The raw source archive spec covers both.
- Normalizing properties, staff, budgets, or planning records.
- Time zone conversion.
  Times stay as the local times the PDF prints.
- Any paid AI API.
- Elasticsearch.
  Admin search for incidents runs in Postgres (requirement 10), and removing Elasticsearch from the stack is its own follow-up task.
- Search across the other entity types, such as properties and planning documents.
  The search spec covers it and still describes Elasticsearch.
- Running AI normalization in the scheduler, or installing the `claude` CLI in the Airflow image.
  Deferred; the `airflow-claude-cli` branch exists, unbuilt, if this is revisited.
- Scheduling the normalization job on the Mac.
  A LaunchAgent is an optional later step, sketched in design.md.
- Alerts by email or chat when a run fails.
  Failures show in Airflow and Logfire.
