# AGENTS.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Project Context

**What this is:** A hyperlocal data platform scraping Lebanon, NH public records (police logs, properties, city staff) into a PostgreSQL + MongoDB backend, with a static Next.js frontend deployed to Cloudflare Pages.

### Architecture

```
scrapers/spiders/         Scrapy spiders
scrapers/items/           Scrapy Item definitions
scrapers/models/          Pydantic validation models (spider → pipeline boundary)
scrapers/pipelines.py     Items → MongoDB / PostgreSQL
dags/                     Airflow DAGs (orchestration)
shared/mongo/             MongoDB client (workspace package)
shared/postgres/          SQLAlchemy models + Alembic migrations (workspace package)
api/                      FastAPI (geocoding)
frontend/web/             Next.js frontend (static, generated JSON)
frontend/admin/           Next.js admin app
frontend/shared/          Shared UI components (@project/ui)
scripts/                  generate_report.sh, deploy.sh
```

### Data Flow

1. `build_daily_urls` spider → scrapes PDF links → saves to MongoDB `urls` collection as `pending`
2. `process_urls` spider → atomically claims `pending` URLs via `find_one_and_update` → downloads PDFs → parses → yields `PoliceLogItem`
3. `PoliceLogPipeline` → validates via Pydantic → upserts to PostgreSQL `log_entries` (keyed on `case_number`)
4. `scripts/generate_report.sh` → exports JSON → committed to `public/data/` → deployed via `wrangler pages deploy`

### Key Patterns

- **Item → Model boundary:** Scrapy Items are untyped dicts. Always validate at the pipeline with `Model.model_validate(dict(item))` before writing to a database.
- **Idempotent writes:** Use `on_conflict_do_nothing` (log entries) or `on_conflict_do_update` (properties, city staff). Never assume a record doesn't exist.
- **Atomic URL claiming:** `find_one_and_update` with `state: pending → in_progress` prevents double-processing across concurrent spider runs.
- **Observability:** Use `logfire.span()` for database writes and PDF processing. Use `logfire.info/warning/error` at key decision points (not every line).
- **Migrations:** Schema changes go through Alembic in `shared/postgres/migrations/`. Never modify tables directly.

### Running Things

```bash
# Start infrastructure
docker compose up -d                          # from repo root

# Run spiders (from scrapers/, where scrapy.cfg lives)
uv run scrapy crawl build_daily_urls
uv run scrapy crawl process_urls -a limit=10

# Tests
uv run pytest

# Generate + deploy
bash scripts/generate_report.sh              # exports JSON and commits
bash scripts/deploy.sh                       # deploys to Cloudflare Pages
```

### Testing Conventions

- Tests live in `scrapers/tests/`
- Spider tests use `scrapy.http.HtmlResponse` / `TextResponse` to build fake responses — no live HTTP
- Pipeline tests use real SQLAlchemy sessions against a test DB, not mocks
- One test file per spider/pipeline/model

## 6. Project Tooling

**Use the project's tools, not generic alternatives.**

- Use `uv` instead of `pip` for all Python package management (`uv add`, `uv run`, `uv sync`)
- Use `docker compose` (not `docker-compose`) for Airflow, Mongo, Postgres
- Use `wrangler pages deploy` (via `bash scripts/deploy.sh`) for Cloudflare Pages deployment
- Use `bun` instead of `npm` for all frontend package management and scripts (`bun install`, `bun add`, `bun run`), from the `frontend/` workspace.
- Check `pyproject.toml` for project scripts before reaching for raw commands

## 7. Frontend

- Check `frontend/shared` for an existing component before adding a new one. Reuse it or extend it rather than adding a near-duplicate.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
