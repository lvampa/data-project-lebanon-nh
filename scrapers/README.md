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

The `mongo_backup` DAG writes a gzipped `mongodump` of the archive's database every day at 2am, and keeps the 7 newest.
It writes to `~/backups/data-project/mongo` on the host, or to `MONGO_BACKUP_DIR` when `.env` sets it.

Create the folder before the first run, as the user that runs Docker:
```bash
mkdir -p ~/backups/data-project/mongo
```
If Docker creates it for the bind mount instead, root owns it, and the Airflow user cannot write to it on Linux or in CI.
The DAG then fails with a message that names the folder.
The folder is on the same disk as the Docker volume unless you point it elsewhere, so it survives a lost volume but not a failed disk.

Check that a backup restores, into the `scraped_data_restore_test` database, which is dropped afterwards.
`mongorestore` is installed in the Airflow image, so run it there, where the folder is `/opt/backups/mongo`:
```bash
docker compose exec -w /opt/project/scrapers airflow-scheduler \
  uv run --frozen python -m maintenance.raw_sources restore-check \
  /opt/backups/mongo/scraped_data-20261107T020000Z.archive.gz
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
