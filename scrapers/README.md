# Scrapers

Web scrapers built with [Scrapy](https://scrapy.org/), orchestrated by Apache Airflow and storing data in MongoDB.

## Stack

- **Scrapy** — scraping framework
- **Apache Airflow** — scheduling and orchestration
- **MongoDB** — data storage
- **[Logfire](https://logfire.pydantic.dev/)** — optional observability (OpenTelemetry-style traces and structured logs; from the Pydantic team)
- **uv** — Python package management
- **pytest** — testing

## Setup

```bash
cp .env.example .env
# edit .env with your credentials
```

Install Python dependencies:
```bash
uv sync
```

Start the infrastructure:
```bash
docker compose up airflow-init   # first time only
docker compose up -d
```

- Airflow UI: http://localhost:8080
- MongoDB: localhost:27017

Initialize Mongo indexes (safe to run multiple times). This creates an index on `urls.state`:
```bash
uv run init-db
```

## Logfire (observability)

The `logfire` package is included so you can add tracing and logging that shows up in the [Logfire](https://logfire.pydantic.dev/) UI. It is optional until you call `logfire.configure()` in your code (for example at process entry or in Scrapy extension setup).

### Configure

**Local machine (recommended):** Logfire keeps authentication under your home directory (`~/.logfire`), not inside this repo. After installing dependencies, run:

```bash
uv run logfire auth
# optional: select the default project for this machine
uv run logfire projects use <your-project-name>
```

Use `uv run logfire whoami` to confirm you are logged in. See the [CLI reference](https://logfire.pydantic.dev/docs/reference/cli/) for `projects list`, `projects new`, regions (`logfire --region us|eu auth`), and the `LOGFIRE_CREDENTIALS_DIR` env var if you need a non-default credentials directory.

**CI or headless environments:** Create a write token in the Logfire UI (**Settings** → **Write tokens**) and set `LOGFIRE_TOKEN` in that environment only—avoid committing it or putting it in the project `.env` if you keep secrets out of the tree.

In code, call `logfire.configure()` once at startup. With CLI auth, `logfire.configure()` with no arguments is usually enough; the SDK reads credentials from your user config.

If your process loads `.env`, you can set non-secret tuning there (see `scrapers/.env.example`)—for example `LOGFIRE_SERVICE_NAME`, `LOGFIRE_ENVIRONMENT`, or `LOGFIRE_SEND_TO_LOGFIRE=false` to stop sending to Logfire locally. Full list: [environment variables](https://logfire.pydantic.dev/docs/reference/configuration/).

You can also set defaults in `pyproject.toml` under `[tool.logfire]`; programmatic `logfire.configure(...)` overrides file and env for the options you pass. Precedence is: **code → environment → `pyproject.toml`**.

## Testing

Run the test suite:
```bash
uv run pytest
```

## Raw source archive

Every original the scrapers download is kept in the MongoDB `raw_sources` collection, as it was downloaded.
These commands read it; run them from `scrapers/`.

Rebuild parcels from their newest archived pages, without downloading anything:
```bash
uv run python -m maintenance.raw_sources replay --source vgsi_parcel
uv run python -m maintenance.raw_sources replay --source vgsi_parcel --parcel 1000 --parcel 1001
```
It prints how many parcels it inserted, updated, and left unchanged, and how many had no usable body.
A parcel whose stored row is more than an hour newer than its newest archived page is skipped and counted, because a scrape the archive missed has already updated it.
Replay stamps each row with its page's own time, so you can run it again after the next parser fix.
It never writes to the archive.

List every version of one source key, newest first, with its fetch time, content hash, size, and seen count:
```bash
uv run python -m maintenance.raw_sources versions --source vgsi_parcel --key 1000
```

Report what the archive holds: versions and size per source, and which finished log PDFs have an archived body.
It also lists parcels with no archived page.
It lists the ones with no body, and exits non-zero while there are any.
```bash
uv run python -m maintenance.raw_sources check
```

### Backups

Two scripts, run by hand, each write a new dated file every time.
Nothing is overwritten or deleted, so clear out old backups yourself.
A failed run deletes its own partial file and exits non-zero.
They write to `~/backups/data-project/mongo` and `~/backups/data-project/postgres` on the host, or to `MONGO_BACKUP_DIR` and `POSTGRES_BACKUP_DIR` when `.env` sets them.

Create the folders before the first run, as the user that runs Docker:
```bash
mkdir -p ~/backups/data-project/mongo ~/backups/data-project/postgres
```
If Docker creates them for the bind mounts instead, root owns them, and the Airflow user cannot write to them on Linux or in CI.
The scripts then fail with a message that names the folder.
The folders are on the same disk as the Docker volumes unless you point them elsewhere, so they survive a lost volume but not a failed disk.

Run them inside the Airflow image, where the dump tools are installed:
```bash
docker compose exec -w /opt/project/scrapers airflow-scheduler \
  uv run --frozen python maintenance/mongo_backup.py
docker compose exec -w /opt/project/scrapers airflow-scheduler \
  uv run --frozen python -m maintenance.postgres_backup
```

Check that a Mongo backup restores, into the `scraped_data_restore_test` database, which is dropped afterwards:
```bash
docker compose exec -w /opt/project/scrapers airflow-scheduler \
  uv run --frozen python -m maintenance.raw_sources restore-check \
  /opt/backups/mongo/scraped_data-20261107T020000Z.archive.gz
```
To restore a Postgres backup into a new database, `app_restored` here, which must not exist yet (the password comes from the container's own environment, so it is never typed):
```bash
docker compose exec airflow-scheduler sh -c '
  export PGPASSWORD="$POSTGRES_PASSWORD"
  createdb --host="$POSTGRES_HOST" --username="$POSTGRES_USER" app_restored &&
  pg_restore --host="$POSTGRES_HOST" --username="$POSTGRES_USER" --no-owner \
    --dbname=app_restored /opt/backups/postgres/app-20261113T221000Z.dump'
```

## Project Structure

```
scrapers/
├── dags/        # Airflow DAGs
├── spiders/     # Scrapy spiders
├── tests/       # pytest tests
├── docker-compose.yml
└── pyproject.toml
```
