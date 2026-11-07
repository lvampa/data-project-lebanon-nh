# Kafka events: requirements

**Status:** Approved
**Created:** 2026-11-07
**Updated:** 2026-11-07

## Introduction

The police log pipeline runs as a chain of Airflow tasks: discover, process, normalize, geocode, build.
Each stage finds its work by scanning Postgres for rows the stage before it left behind.
That works, but it couples the stages to each other's tables and to the daily schedule.
A PDF stored at 06:10 waits for the normalization task to come round, and a new consumer of "entries were stored" has to learn the `log_entries` query and get its own slot in the DAG.

This feature adds Kafka as the way one stage tells the next that something happened.
The first slice covers one boundary: when the process job stores a PDF's entries, it publishes an `entries.stored` event, and a long-running consumer picks it up and runs AI normalization and geocoding for those entries.
Kafka carries events; it is not the work queue.
The Postgres `pdf_urls` queue, with its leases and attempt counts, stays as it is.
Airflow keeps scheduling and monitoring the batch stages, and the scheduled normalization job stays as the backstop that catches anything an event missed.

Success is that a PDF's entries are normalized and placed on the map within minutes of being stored, with no change to what Postgres holds, and that a second consumer of the same event could be added without touching the process job.
Everything runs locally in Docker at no cost.
The point of Kafka here is decoupling the stages, and the interview story that goes with it, not throughput.

## Glossary

- **Event:** One message on a Kafka topic that says something happened, with the key and fields in the design.
- **`entries.stored`:** The event the process job publishes after it commits a PDF's entries to `log_entries`.
- **Producer:** The code in `PoliceLogPipeline` that publishes events.
- **Consumer:** The `normalizer` compose service that reads `entries.stored` and runs normalization and geocoding.
- **Consumer group:** Kafka's record of how far a named set of consumers has read a topic.
- **Offset:** A message's position in a topic partition; committing an offset marks everything before it as done for that consumer group.
- **Dead-letter topic (DLT):** The topic where the consumer puts an event it could not process, so nothing is lost and the operator can look.
- **Schema version:** The integer in every event that says which Pydantic model describes it.
- **Content hash:** The SHA-256 of a log PDF's bytes, as recorded on `pdf_urls.content_hash` by the police log pipeline.
- **Normalization job:** The scheduled job from the police log pipeline spec that normalizes incident types and locations with AI.
- **Geocode job:** The scheduled job from the police log pipeline spec that places normalized locations on the map.
- **Human row:** A normalization whose source is `human`, which no job may change.

## Requirements

### Requirement 1: Run Kafka locally

**User story:** As the operator, I want Kafka to start with the rest of the stack and need no setup, so that events work on a laptop at no cost.

#### Acceptance criteria

1. THE compose file SHALL run one Kafka broker from the image `apache/kafka:4.3.2`, in KRaft mode, with no ZooKeeper.
2. THE broker SHALL keep its data on a named Docker volume, so that events survive `docker compose down` and `up`.
3. THE compose file SHALL give the broker a healthcheck, and the Airflow services and the consumer SHALL wait for it to pass before starting.
4. THE broker SHALL NOT create topics on first use.
5. WHEN the stack starts, THE topic init step SHALL create every topic in the design, with its partition count and retention, and SHALL succeed when they already exist.
6. THE broker SHALL be reachable as `kafka:9092` from other compose services and as `localhost:29092` from the host, so that tests on the host and services in Docker use the same broker.
7. THE broker SHALL keep each event for 7 days.
8. THE compose file SHALL NOT run Kafka with more than one broker, a schema registry, Kafka Connect, or any Confluent-only service.

### Requirement 2: Publish an event when a PDF's entries are stored

**User story:** As a downstream stage, I want to be told when a PDF's entries land in Postgres, so that I can act on them without scanning tables or waiting for a schedule.

#### Acceptance criteria

1. WHEN `PoliceLogPipeline` commits a PDF's entries and marks its URL record `complete`, THE producer SHALL publish one `entries.stored` event for that PDF, after the commit returns.
2. THE producer SHALL key the event on the PDF's content hash.
3. THE event SHALL carry the schema version, an event ID, the time it was published, the content hash, the `pdf_urls` ID, the source URL, and the case numbers of every entry inserted or updated by that ingest.
   The content hash is the SHA-256 of the PDF bytes, computed by the process spider until the archive middleware supplies it.
4. IF the ingest inserted or updated no entries, THEN THE producer SHALL NOT publish an event for that PDF.
5. IF the transaction rolls back, THEN THE producer SHALL NOT publish an event for that PDF.
6. THE producer SHALL NOT make the process job wait for the broker's acknowledgement of each event before the spider moves on to the next PDF.
7. WHEN the spider closes, THE producer SHALL wait up to 10 seconds for every published event to be acknowledged.
8. IF any event is not acknowledged by then, THEN THE producer SHALL log one error with the count of failed events and their case numbers, and THE process job SHALL exit with a non-zero status.
9. IF an event is not acknowledged, THEN THE producer SHALL leave the PDF's URL record `complete` and its entries stored, so that the scheduled normalization job picks the entries up on its next run.
10. THE producer SHALL NOT check that the broker is reachable before the run starts.
11. THE reprocess job SHALL NOT publish events; the scheduled normalization job covers reprocessed entries, as police log pipeline criterion 4.8 says.
12. THE producer SHALL record each published event in a `logfire` span with the content hash and the number of case numbers.

### Requirement 3: Describe events with versioned schemas

**User story:** As a developer, I want every event's shape written down as a Pydantic model with a version, so that a producer and a consumer built at different times still agree.

#### Acceptance criteria

1. THE event value SHALL be UTF-8 JSON produced by a Pydantic model, and THE event key SHALL be the content hash as UTF-8 text.
2. EVERY event SHALL carry an integer `schema_version` field in its value and a `schema_version` header on the message.
3. EVERY event SHALL carry an `event_type` header, `entries.stored` for this slice.
4. THE producer SHALL validate an event with its model before publishing it.
5. THE consumer SHALL validate an event with the model for its `schema_version` before acting on it.
6. WHEN a field is added to an event with a default, THE schema version SHALL stay the same, and consumers on the old model SHALL keep reading the event.
7. WHEN a field is removed, renamed, or changes type, THE schema version SHALL go up by one, and THE consumer SHALL read both the old and the new version until the old one has left the topic.
8. IF an event's value is not valid JSON, has no `schema_version`, or has a version the consumer does not know, THEN THE consumer SHALL send it to the dead-letter topic without retrying and move on.

### Requirement 4: Normalize and geocode new entries as they arrive

**User story:** As Connor, I want a PDF's entries normalized and placed on the map soon after they are stored, so that the admin shows normalized values the same morning instead of after the next scheduled run.

#### Acceptance criteria

1. THE consumer SHALL run as one long-running compose service, `normalizer`, that restarts when it stops.
2. THE consumer SHALL read `entries.stored` in one consumer group, `normalizer`.
3. WHEN the consumer receives an `entries.stored` event, THE consumer SHALL normalize the distinct raw incident types and raw locations of the entries named by its case numbers, then geocode the locations among them that need it, with the same rules, limits, and answer checks as police log pipeline requirements 5, 6, 8, and 9.
4. THE consumer SHALL NOT change a human row, including its coordinates.
5. THE consumer SHALL record every AI call in the archive as police log pipeline criterion 8.13 says.
6. WHEN the consumer finishes an event, THE consumer SHALL commit the event's offset, and SHALL NOT commit it before.
7. IF the consumer receives the same event twice, or two events naming the same case number, THEN THE consumer SHALL produce the same rows as if it had received each once.
8. WHEN the consumer restarts, THE consumer SHALL continue from the last committed offset, and SHALL start from the oldest event the topic holds when the group has no committed offset.
9. THE consumer SHALL process one event at a time.
10. THE consumer SHALL stay in its group while it processes one event that takes up to 20 minutes.
11. THE consumer SHALL record each event it handles in a `logfire` span with the content hash, the number of raw values sent to AI, the number of locations geocoded, and the outcome.
12. THE scheduled normalization and geocode jobs SHALL keep running as they do, so that any entry an event missed is still normalized.
13. WHEN the consumer receives a shutdown signal, THE consumer SHALL finish the event in hand, commit its offset, and exit with status 0.

### Requirement 5: Keep failed events

**User story:** As the operator, I want an event the consumer could not handle kept where I can see it, so that a bad PDF or a dead AI backend never loses an event or stops the ones behind it.

#### Acceptance criteria

1. IF handling an event fails, THEN THE consumer SHALL try it again up to 3 times in total, waiting 1, 5, and 25 seconds between tries.
2. IF the third try fails, THEN THE consumer SHALL publish the event to the dead-letter topic `police-log.entries-stored.dlt`, with the original key and value and headers that name the error, the number of tries, the time, and the consumer group, then commit the offset and move on.
3. IF the AI backend reports it is not logged in or has hit a usage limit, THEN THE consumer SHALL NOT retry, SHALL send the event to the dead-letter topic, and SHALL log one error that says so.
4. IF publishing to the dead-letter topic fails, THEN THE consumer SHALL NOT commit the offset and SHALL exit with a non-zero status, so that it restarts and reads the event again.
5. THE operator SHALL be able to list the dead-letter topic's events, newest first, with each one's content hash, error, and time, in one command.
6. THE operator SHALL be able to replay one dead-letter event or all of them to `police-log.entries-stored` in one command.
7. WHEN an event is replayed, THE replay SHALL keep the original key and value and SHALL add a header with the replay time.

### Requirement 6: Test against a real broker without touching live topics

**User story:** As Connor, I want the Kafka code tested against a real broker in CI and on my laptop, so that the tests prove publishing and consuming work and never touch live events.

#### Acceptance criteria

1. THE test suite SHALL run producer and consumer tests against a real Kafka broker, with no fake broker.
2. EACH test that uses the broker SHALL create its own topic, named with a `test.` prefix and a random suffix, and its own consumer group, and SHALL delete the topic when it ends.
3. THE test fixtures SHALL refuse to delete a topic whose name does not start with `test.`.
4. THE CI python job SHALL start the broker next to Postgres before running pytest.
5. THE pipeline tests SHALL use a fake producer that records what would have been published, so that they still need no broker.
6. THE consumer tests SHALL use the normalization job's fake AI backend and fake geocoder, so that no test makes a real AI call or a request to Nominatim.
7. WHEN `KAFKA_BOOTSTRAP_SERVERS` is unset, THE tests that need the broker SHALL be skipped with a message that names the variable, and every other test SHALL run.

## Out of scope

- A `pdf.archived` event, published when the archive middleware stores a PDF, with parsing moved out of the spider into a consumer.
  This is the next slice; this one proves the pattern on the boundary that has consumers ready for it.
- Events for other sources: a property upsert feeding the LLC lookup, city staff, officers, budgets.
- Replacing the Postgres `pdf_urls` queue with Kafka.
  Kafka has no per-message lease or attempt count, and the queue works.
- The outbox pattern and a `published_at` sweep.
  The design records why.
- Change data capture with Debezium, Kafka Connect, or any CDC tool.
- A schema registry and Avro or Protobuf encodings.
- Exactly-once delivery and Kafka transactions; the consumers are idempotent instead.
- Running consumers as Airflow tasks or with the Airflow Kafka provider.
- More than one broker, authentication, TLS, or a hosted Kafka.
- A UI for topics; `kafka-console-consumer.sh` in the broker container is enough.
- dbt builds triggered by events; the daily build stays on the schedule.
