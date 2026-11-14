# Data-Project-Lebanon
ETL, Infrastructure, Presentation Dashboards for data made public by the city of Lebanon, NH

## Tests

Run every suite from the repo root with `uv run pytest`.
A test that opens a database session has to ask for the `db_session` or `db_connection` fixture; without one the session has no database and the test fails.
Database tests run against a Postgres database named `app_test`, never `app`.
The test run creates `app_test` if it is missing and applies the migrations to it.
Each test runs inside a transaction that is rolled back, so the database stays empty.
Postgres has to be running: `docker compose up -d postgres`.
MongoDB tests do the same with a database named `scraped_data_test`, never `scraped_data`; start it with `docker compose up -d mongo`, and set `TEST_MONGO_DB` to use another `_test` name.
The pre-push hook runs the tests, so it needs Postgres up too.
Set `TEST_POSTGRES_DB` to use another database; the run stops unless its name ends in `_test`.
The run leaves `app_test` at the newest migration of the branch you tested.
Before testing an older branch, drop `app_test` or point `TEST_POSTGRES_DB` at another `_test` database, or the upgrade fails on a revision that branch does not have.

## Removing the old Elasticsearch data

Elasticsearch is gone from the stack, but a volume made by an earlier `docker compose up` stays on disk.
Stop the old containers, then delete the volume:
```bash
docker compose down --remove-orphans
docker volume rm data-project_elasticsearch_data
```
The volume name is the folder name plus `_elasticsearch_data`; `docker volume ls` shows it.
