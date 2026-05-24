# Scrapers — Claude Context

## Stack
- Python managed with `uv` (use `uv add` to install packages, never `pip`)
- Scrapy for scraping
- MongoDB for storage (connection via env vars)
- Airflow DAGs in `./dags/`
- Logfire (`logfire`) for optional observability — local auth lives in `~/.logfire` via `logfire auth` / `logfire projects use`; use `LOGFIRE_TOKEN` only where CLI auth is not possible (e.g. CI). See [CLI](https://logfire.pydantic.dev/docs/reference/cli/), [configuration](https://logfire.pydantic.dev/docs/reference/configuration/), and `README.md` in this folder

## Project structure
- `spiders/` — one spider per source
- `items/` — Scrapy Item definitions (one file per pipeline/source)
- `models/` — Pydantic models for MongoDB documents
- `pipelines.py` — item pipelines (one class per item type)
- `settings.py`, `middlewares.py`, `scrapy.cfg` — Scrapy project config at root
- `dags/` — Airflow DAGs that orchestrate spider runs via `BashOperator` or `PythonOperator`
- `shared/mongo/` — shared MongoDB client package

## Conventions
- Each spider targets one source
- Use `.env` for secrets — never hardcode credentials; prefer `~/.logfire` for Logfire CLI auth instead of putting write tokens in the project
- All new code must use type annotations

## Testing
- Tests live in `./tests/`, or in `tests/` within each package (e.g. `shared/mongo/tests/`)
- Write tests for all new code — spiders, shared utilities, and helpers
- Tests must pass before considering any feature complete
- Run with: `uv run pytest`

## Running locally
```bash
docker compose up -d          # start mongo + airflow
uv run scrapy crawl <spider>  # run a spider directly
uv run pytest                 # run tests
```
