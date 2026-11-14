# Data-Project-Lebanon
ETL, Infrastructure, Presentation Dashboards for data made public by the city of Lebanon, NH

## Database migrations

Schema changes go through Alembic, and you apply them by hand, along with the MongoDB indexes.
Nothing runs them for you at startup.

Start Postgres and MongoDB, then run these two commands from the repo root:
```bash
docker compose up -d postgres mongo
uv run alembic -c shared/postgres/alembic.ini upgrade head
uv run python -c "from mongo import init_indexes; init_indexes()"
```
The first applies the Postgres migrations.
The second creates the MongoDB indexes, and is safe to run again.
Run both again after you pull a branch that adds a migration or an index.

They read `POSTGRES_*` and `MONGO_*` from your shell, and fall back to the local compose values.
If your `.env` sets other values, load them first with `set -a; . ./.env; set +a`.

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
