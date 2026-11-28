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
- `docker compose ps` shows the API server, DAG processor and scheduler as `healthy` once they are up.
- Log in with `AIRFLOW_USER` and `AIRFLOW_PASSWORD` from `.env`.
- Airflow 3 starts with an empty `airflow` database. Create the `r2_data` Connection again in the UI, and keep the same `AIRFLOW_FERNET_KEY` in `.env`, or Airflow cannot decrypt the Connections it stores.
- The Airflow UI shows times in New York time. DAG schedules are still UTC.
- MongoDB: localhost:27017

Initialize Mongo indexes (safe to run multiple times). This creates an index on `urls.state`:
```bash
uv run init-db
```

## Logfire (observability)

The `logfire` package is included so you can add tracing and logging that shows up in the [Logfire](https://logfire.pydantic.dev/) UI. Every entry point calls `bootstrap(service_name)` from `shared/bootstrap`, which loads `.env` and then configures Logfire. Call it once at startup instead of calling `logfire.configure()` yourself. The first call wins, so a later one (the Scrapy extension, for example) keeps the first service name.

### Configure

**Local machine (recommended):** Logfire keeps authentication under your home directory (`~/.logfire`), not inside this repo. After installing dependencies, run:

```bash
uv run logfire auth
# optional: select the default project for this machine
uv run logfire projects use <your-project-name>
```

Use `uv run logfire whoami` to confirm you are logged in. See the [CLI reference](https://logfire.pydantic.dev/docs/reference/cli/) for `projects list`, `projects new`, regions (`logfire --region us|eu auth`), and the `LOGFIRE_CREDENTIALS_DIR` env var if you need a non-default credentials directory.

**CI or headless environments:** Create a write token in the Logfire UI (**Settings** → **Write tokens**) and set `LOGFIRE_TOKEN` in that environment only—avoid committing it or putting it in the project `.env` if you keep secrets out of the tree.

With CLI auth, `bootstrap` needs nothing more; the SDK reads credentials from your user config.

If your process loads `.env`, you can set non-secret tuning there (see `scrapers/.env.example`) - for example `LOGFIRE_ENVIRONMENT` or `LOGFIRE_SEND=never` to stop sending to Logfire locally. Full list: [environment variables](https://logfire.pydantic.dev/docs/reference/configuration/).

Set `LOG_FILE=tmp/logs/dev.log` to also append everything to a file while you debug a hand run: Scrapy's log lines and the `logfire` messages and spans. It is off when unset, so containers and CI log to stdout only. Warnings and errors from stdlib logging, Scrapy's included, also go to Logfire.

You can also set defaults in `pyproject.toml` under `[tool.logfire]`; arguments passed in code (`bootstrap` sets `service_name`) override file and env for the options you pass. Precedence is: **code → environment → `pyproject.toml`**.

## Testing

Run the test suite:
```bash
uv run pytest
```

## Raw source archive

Every original the scrapers download is kept in the MongoDB `raw_sources` collection, as it was downloaded.
These commands read it; run them from `scrapers/`.

Build the property tables from the archived parcel pages, without downloading anything.
Run it from `scrapers/`:
```bash
uv run python -m maintenance.build_properties
```
It parses the newest archived page of each parcel seen in the latest finished `vgsi_property` crawl, runs the quality checks, and replaces `properties` and `property_sales` in one transaction.
When a check fails it writes nothing, logs why, and exits 1.
Run it again after any parser fix.

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

## Police logs

These commands run from `scrapers/`.

Reparse archived log PDFs after a parser fix, without downloading anything:
```bash
uv run python -m maintenance.reprocess_police_logs --all
uv run python -m maintenance.reprocess_police_logs --from 2026-05-01 --to 2026-05-31
```
It reads the newest archived PDF of each `complete` or `error` URL record, in log date order.
A record with no archived original goes back to `pending`, so the process job downloads it again.
It exits non-zero when the archive is unreachable, when a record failed, or when the process job holds the lock.
The `police_log_reprocess` DAG runs the same command by hand, with `date_from` and `date_to` params.

Changing the parser means bumping `PARSER_VERSION` in `parsers/police_log.py` and reprocessing.
So does changing the disposition list in `parsers/dispositions.py`, and so does a pypdf upgrade.

List the URL records the process job gave up on, and send chosen ones back to `pending`:
```bash
uv run python -m maintenance.police_logs errors
uv run python -m maintenance.police_logs reset https://www.lebanonnh.gov/DocumentCenter/View/23007/2026-05-11
```
`reset` also restarts the attempt count.

List entries whose text ended in no known disposition:
```bash
uv run python -m maintenance.police_logs unmatched-dispositions
```
Add each new ending to `parsers/dispositions.py`, then bump the parser version and reprocess.

## Project Structure

```
scrapers/
├── dags/        # Airflow DAGs
├── spiders/     # Scrapy spiders
├── tests/       # pytest tests
├── docker-compose.yml
└── pyproject.toml
```
