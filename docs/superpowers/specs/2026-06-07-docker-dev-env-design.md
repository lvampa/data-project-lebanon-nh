# Docker Dev Environment Design

**Date:** 2026-06-07  
**Scope:** Local development infrastructure only

---

## Overview

Consolidate the project's Docker configuration into a single `compose.yml` at the repo root that spins up all infrastructure services. Application code (Next.js, FastAPI, Scrapy spiders) runs on the host as usual — Docker provides only the data and orchestration layer.

---

## Files

| File | Purpose |
|---|---|
| `compose.yml` | Repo root; replaces `scrapers/docker-compose.yml` |
| `docker/Dockerfile.airflow` | Custom Airflow image with `uv` installed |
| `.env` | Local secrets — gitignored |
| `.env.example` | Committed template with all required vars |

---

## Services

### `mongo`
- Image: `mongo:8`
- Port: `27017:27017`
- Volume: `mongo_data:/data/db`
- No change from current setup

### `postgres`
- Image: `postgres:16`
- Port: `5432:5432` (now exposed to host for DB client access)
- Volume: `postgres_data:/var/lib/postgresql/data`
- Single database named `app` (replaces `police_logs`)
- Credentials: `POSTGRES_USER=app`, `POSTGRES_PASSWORD=app`, `POSTGRES_DB=app`
- Healthcheck: `pg_isready -U app`
- Used by both Airflow (metadata) and the application (incidents, stats, addresses, categories)

### `airflow-init`
- Built from `docker/Dockerfile.airflow`
- Runs once: `airflow db migrate` + `airflow users create`
- Depends on `postgres` healthy

### `airflow-webserver`
- Built from `docker/Dockerfile.airflow`
- Port: `8080:8080`
- Depends on `postgres` healthy
- Mounts (see Volume Strategy below)

### `airflow-scheduler`
- Built from `docker/Dockerfile.airflow`
- No exposed port
- Same mounts as webserver

---

## Custom Airflow Image

**`docker/Dockerfile.airflow`**

```dockerfile
FROM apache/airflow:2.10.4
USER root
RUN pip install uv
USER airflow
```

`uv` is installed system-wide so it's available to the `airflow` user when DAG tasks run.

### Virtual Environment Isolation

To prevent the container venv from conflicting with the host venv (different OS/Python), all Airflow containers set:

```
UV_PROJECT_ENVIRONMENT=/opt/airflow/.scrapers-venv
```

`uv run` writes the venv to this Airflow-owned path rather than to `scrapers/.venv`. The container venv is rebuilt automatically on first `docker compose up` and persists for the lifetime of the container.

---

## Volume Strategy

Selective mounts — only what Airflow needs to resolve the uv workspace and run spiders:

| Mount | Host path | Container path | Mode |
|---|---|---|---|
| DAGs | `./scrapers/dags` | `/opt/airflow/dags` | rw |
| Scrapers code | `./scrapers` | `/opt/project/scrapers` | rw |
| Shared packages | `./shared` | `/opt/project/shared` | rw |
| Workspace root | `./pyproject.toml` | `/opt/project/pyproject.toml` | ro |
| Lock file | `./uv.lock` | `/opt/project/uv.lock` | ro |
| Airflow logs | `airflow_logs` volume | `/opt/airflow/logs` | rw |

`web/` and `api/` are intentionally excluded — they are not needed by Airflow and mounting them would drag in `node_modules` and Python caches, causing significant slowness on macOS.

---

## DAG Commands

Both DAGs update their `bash_command` to reference the new project path:

**Before:**
```bash
cd /opt/scrapers && uv run scrapy crawl <spider>
```

**After:**
```bash
cd /opt/project/scrapers && uv run scrapy crawl <spider>
```

---

## Environment Variables

**`.env.example`** (committed):
```bash
MONGO_USER=admin
MONGO_PASSWORD=changeme
MONGO_DB=scraped_data
AIRFLOW_USER=admin
AIRFLOW_PASSWORD=admin
```

All variables use `${VAR:-default}` fallbacks in `compose.yml` so devs without a `.env` get working defaults.

Airflow containers receive Mongo and Postgres connection details via environment so DAGs can pass them to spiders at runtime.

---

## Connection Strings

| Service | Connection (from host) |
|---|---|
| MongoDB | `mongodb://admin:changeme@localhost:27017` |
| PostgreSQL | `postgresql://app:app@localhost:5432/app` |
| Airflow UI | `http://localhost:8080` |

---

## What Is Not Containerized

| Component | How to run |
|---|---|
| Scrapy spiders | `uv run scrapy crawl <spider>` from `scrapers/` |
| FastAPI admin | `uv run uvicorn api.main:app --reload` from repo root |
| Next.js web app | `npm run dev` from `web/` |
| Static public site | Deployed to Cloudflare Pages via `wrangler` — no local server needed |

---

## Out of Scope

- Production deployment (no prod compose, no Kubernetes manifests)
- CI configuration
- User authentication for the web app
- Containerizing the FastAPI or Next.js services
