# Data-Project-Lebanon
ETL, Infrastructure, Presentation Dashboards for data made public by the city of Lebanon, NH

## Database migrations

Schema changes go through Alembic, and you apply them by hand.
Nothing runs them for you at startup.

Start Postgres, then run this from the repo root:
```bash
docker compose up -d postgres
uv run alembic -c shared/postgres/alembic.ini upgrade head
```
It reads `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` and `POSTGRES_DB` from your shell, and falls back to `app`, `app`, `localhost`, `5432` and `app`.
If your `.env` sets other values, load them first with `set -a; . ./.env; set +a`.
Run it again after you pull a branch that adds a migration.

## Tests

Run every suite from the repo root with `uv run pytest`.
A test that opens a database session has to ask for the `db_session` or `db_connection` fixture; without one the session has no database and the test fails.
Database tests run against a Postgres database named `app_test`, never `app`.
The test run creates `app_test` if it is missing and applies the migrations to it.
Each test runs inside a transaction that is rolled back, so the database stays empty.
Postgres has to be running: `docker compose up -d postgres`.
The pre-push hook runs the tests, so it needs Postgres up too.
Set `TEST_POSTGRES_DB` to use another database; the run stops unless its name ends in `_test`.
The run leaves `app_test` at the newest migration of the branch you tested.
Before testing an older branch, drop `app_test` or point `TEST_POSTGRES_DB` at another `_test` database, or the upgrade fails on a revision that branch does not have.
