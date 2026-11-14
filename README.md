# Data-Project-Lebanon
ETL, Infrastructure, Presentation Dashboards for data made public by the city of Lebanon, NH

## Database migrations

Schema changes go through Alembic, and you apply them by hand, along with the MongoDB indexes.
Nothing runs them for you at startup.

Start Postgres and MongoDB, then run this from the repo root:
```bash
docker compose up -d postgres mongo
uv run migrate
```
It applies the Postgres migrations, then creates the MongoDB indexes, and stops at the first failure.
It is safe to run again, and you should after you pull a branch that adds a migration or an index.

It reads `POSTGRES_*` and `MONGO_*` from your shell or your `.env`, and falls back to the local compose values.
For any other Alembic command, `uv run alembic -c shared/postgres/alembic.ini ...` still works.

## Normalizing with AI

The AI normalizing runs by hand on your Mac, with your own Claude login.
No container runs it, and no Claude token goes in `.env`.

```bash
docker compose up -d postgres mongo
uv sync
uv run normalize
uv run geocode
```

The first command gives incident types a category and a plain name, and gives locations a clean address and a kind.
The second puts the normalized locations on the map.
Run the VGSI scrape first, because the location step builds its street list from the parcel table, and makes no location AI calls while that table is empty.

The job takes `--field incident_type` or `--field location` to do one field, and `--redo` to ask again for rows that are not on the current prompt version.
A value goes to the AI once, so running it again only sends what is new, or what failed.
Each run makes at most 10 AI calls of up to 50 values.

Both commands refuse to run while another police log job holds the lock, and say so.
The job refuses to run when `ANTHROPIC_API_KEY` is set, because the CLI would bill that key instead of your plan.
Both read `POSTGRES_*` and `MONGO_*` from your shell, as the migration commands do.

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
