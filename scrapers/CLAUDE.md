# Scrapers — Claude Context

## Stack
- Python managed with `uv` (use `uv add` to install packages, never `pip`)
- Scrapy for scraping
- MongoDB for storage (connection via env vars)
- Airflow DAGs in `./dags/`

## Conventions
- Spiders go in `./spiders/`
- Each spider targets one source
- DAGs in `./dags/` orchestrate spider runs via `BashOperator` or `PythonOperator`
- Use `.env` for secrets — never hardcode credentials

## Running locally
```bash
docker compose up -d          # start mongo + airflow
uv run scrapy crawl <spider>  # run a spider directly
```
