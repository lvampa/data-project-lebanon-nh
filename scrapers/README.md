# Scrapers

Web scrapers built with [Scrapy](https://scrapy.org/), orchestrated by Apache Airflow and storing data in MongoDB.

## Stack

- **Scrapy** — scraping framework
- **Apache Airflow** — scheduling and orchestration
- **MongoDB** — data storage
- **uv** — Python package management

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

## Project Structure

```
scrapers/
├── dags/        # Airflow DAGs
├── spiders/     # Scrapy spiders
├── docker-compose.yml
└── pyproject.toml
```
