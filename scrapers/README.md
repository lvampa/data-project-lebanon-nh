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

## Project Structure

```
scrapers/
├── dags/        # Airflow DAGs
├── spiders/     # Scrapy spiders
├── tests/       # pytest tests
├── docker-compose.yml
└── pyproject.toml
```
