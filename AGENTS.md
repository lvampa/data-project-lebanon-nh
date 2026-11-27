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
scrapers/pipelines.py     Items → PostgreSQL
dags/                     Airflow DAGs (orchestration)
shared/locations/         Canonical address rules and geocoding (workspace package)
shared/mongo/             MongoDB client (workspace package)
shared/postgres/          SQLAlchemy models + Alembic migrations (workspace package)
api/                      FastAPI (geocoding)
frontend/web/             Next.js frontend (static, generated JSON)
frontend/admin/           Next.js admin app
frontend/shared/          Shared UI components (@project/ui)
scripts/                  generate_report.sh, deploy.sh
```

### Data Flow

1. `build_daily_urls` spider → scrapes PDF links → inserts them into PostgreSQL `pdf_urls` as `pending`
2. `process_urls` spider → claims `pending` URLs with `FOR UPDATE SKIP LOCKED` (recording `claimed_at` and `attempts`) → downloads PDFs → extracts text → yields one `PoliceLogPdfItem` per PDF carrying its text
3. `PoliceLogPipeline` → calls `ingest_pdf_url` in `scrapers/ingest/police_log.py`, which parses the text, validates each entry via Pydantic, and upserts `log_entries` (keyed on `case_number`) → the URL becomes `complete` in the same commit, or `error` with a kind (`download`, `parse`, `save`)
4. `scripts/generate_report.sh` exports JSON into `data/export/` (gitignored). The site's code deploys from CI on merge to main through `scripts/deploy.sh`, with no data in the build. `scripts/deploy-data.sh` holds unsafe person locations (`privacy-holds mark`), exports, runs `uv run check-export`, and syncs the folder to R2 (see `docs/specs/site-deploy/design.md`)

### Key Patterns

- **Item → Model boundary:** Scrapy Items are untyped dicts. Always validate at the pipeline with `Model.model_validate(dict(item))` before writing to a database.
- **Idempotent writes:** Use `on_conflict_do_update` (log entries, properties, city staff). Never assume a record doesn't exist.
- **Atomic URL claiming:** an `UPDATE ... WHERE id IN (SELECT ... FOR UPDATE SKIP LOCKED)` moves `pending → in_progress`, so concurrent runs never claim the same URL.
- **One run of a job at a time:** advisory locks in `shared/postgres/src/postgres/lock.py`, one per conflict. `police_log_parse` is shared by the process runner and the reprocess job, so an old parse cannot overwrite a new one. `normalize` stops two runs spending the same AI calls, and `geocode` stops two runs doubling the Nominatim rate. Jobs on different locks run together.
- **Observability:** Use `logfire.span()` for database writes and PDF processing. Use `logfire.info/warning/error` at key decision points (not every line).
- **Migrations:** Schema changes go through Alembic in `shared/postgres/migrations/`. Never modify tables directly.

### Running Things

```bash
# Start infrastructure
docker compose up -d                          # from repo root

# Run spiders (from scrapers/, where scrapy.cfg lives)
uv run scrapy crawl build_daily_urls
uv run python run_process_urls.py --limit 10   # exits non-zero if a PDF fails

# Tests
uv run pytest

# Generate the data for local dev
bash scripts/generate_report.sh              # exports JSON to data/export

# Publish the data to R2. By hand it needs R2_BUCKET, CLOUDFLARE_ACCOUNT_ID and AWS_PROFILE
# (`aws configure --profile <name>`). The Airflow publish_data DAG runs it with the r2_data
# Connection, made in the Airflow UI; see docs/specs/site-deploy/design.md.
bash scripts/deploy-data.sh [--dry-run]      # export, check, then sync

# Hold person locations that are not clearly safe, and release them after a look
uv run privacy-holds list                    # id, kind and raw text, for your terminal only
uv run privacy-holds handled <id> [<id>...]

# Local dev has no data server. Without NEXT_PUBLIC_DATA_URL the data pages show the error
# state. Set it to the R2 URL in frontend/web/.env.local to read live data.

# Deploy by hand (CI runs the same script on merge to main)
bash scripts/deploy.sh [--dry-run]           # ships whatever is checked out
```

### Testing Conventions

- Tests live in `scrapers/tests/`
- Spider tests use `scrapy.http.HtmlResponse` / `TextResponse` to build fake responses, with no live HTTP
- Pipeline tests use real SQLAlchemy sessions against a test DB, not mocks
- One test file per spider/pipeline/model

## 6. Project Tooling

**Use the project's tools, not generic alternatives.**

- Use `uv` instead of `pip` for all Python package management (`uv add`, `uv run`, `uv sync`)
- Use `docker compose` (not `docker-compose`) for Airflow, Mongo, Postgres
- The Dockerfiles take uv from its image (`COPY --from=ghcr.io/astral-sh/uv`), the same version as `.github/workflows/ci.yml`, and install dependencies from the lockfile before the source is copied.
- `.dockerignore` leaves out `frontend/`, so an image that needs a file from there has to stop ignoring it first.
- Airflow shows times in `America/New_York` (`AIRFLOW__CORE__DEFAULT_TIMEZONE` in `compose.yml`). DAG schedules stay UTC, because `dags/build_dags.py` gives every DAG a UTC `start_date`.
- Cloudflare Pages deploys from `.github/workflows/deploy.yml` on merge to main, and the workflow only runs `scripts/deploy.sh`. Use that script, not a bare `wrangler pages deploy`. A redeploy is "Re-run all jobs" on the last run (re-running an older run rolls production back to that commit; use Pages Rollback for that), and another branch deploys with a local `scripts/deploy.sh`, run from the repo root.
- Use `bun` instead of `npm` for all frontend package management and scripts (`bun install`, `bun add`, `bun run`), from the `frontend/` workspace.
- Check `pyproject.toml` for project scripts before reaching for raw commands
- CI (`.github/workflows/ci.yml`) runs the pre-push checks plus Rust and, when Docker inputs change, the image builds; `ci-ok` is the one required check.
- Use Pyrefly for Python type checking (`uv run pyrefly check`). New code is strict; files on the not-yet-strict list in `pyproject.toml` are not, and only come off it.

## 7. Frontend

- Check `frontend/shared` for an existing component before adding a new one. Reuse it or extend it rather than adding a near-duplicate.
- Read `docs/frontend/brand.md` before changing styles, the header, the footer, or charts.
- Use the tokens in `frontend/shared/styles/` (`text-display-*`, `eyebrow`, color names) instead of arbitrary values like `text-[34px]`.
- Run `bun run check` from `frontend/` before pushing; the pre-push hook runs it too.

## 8. Specs and plans

A feature's `design.md` is tracked in the repo.
Its requirements, its task list and implementation plans are working files for you, and are not tracked.

- Write the spec before coding the feature.
- Save implementation plans to `.claude/plans/YYYY-MM-DD-<name>.md`, which is not tracked.
- Delete a plan once it is implemented, after updating the feature's `design.md` to match what was built.

### Spec layout

Each feature gets `docs/specs/<feature-name>/` with a short kebab-case name and three files, written and reviewed in order:

1. `requirements.md`: what the feature must do and why. Untracked.
2. `design.md`: how it will be built. Tracked, and kept short.
3. `tasks.md`: the design broken into steps that can be checked off. Untracked.

`.gitignore` ignores `requirements.md` and `tasks.md`, so they can live in the folder as working copies.

Each file starts with the title and a status block, kept the same across the three files:

```markdown
# City budgets: requirements

**Status:** Draft | Approved | In progress | Done
**Created:** 2026-06-07
**Updated:** 2026-10-16
```

### requirements.md

Sections: Introduction, Glossary (if needed), Requirements, Out of scope.
Each requirement has a user story and numbered acceptance criteria in EARS form:

```markdown
### Requirement 1: Discover budget PDFs

**User story:** As an operator, I want new budget PDFs found automatically, so that the data stays current without manual checks.

#### Acceptance criteria

1. WHEN the discovery job runs, THE spider SHALL record every Budget Book and Line Items PDF linked from the index page.
2. IF a PDF for a fiscal year and document type is already recorded, THEN THE pipeline SHALL update its URL instead of adding a duplicate.
```

- EARS patterns: `THE <component> SHALL ...`, `WHEN <trigger>, ...`, `WHILE <state>, ...`, `IF <condition>, THEN ...`, `WHERE <feature is present>, ...`.
- One behavior per criterion, testable, with numbers instead of adjectives.
- Name the component, not "the system".
- Cover failure and empty cases.
- Number criteria `<requirement>.<criterion>`, like `2.3`, so tasks can cite them.
- Requirements describe observable behavior; implementation choices go in the design.

### design.md

A few screens, not a full specification: what the feature is, the data flow, and the key decisions with what was rejected and why.
Add a short data model, failure handling or testing section only when it earns its place, and an Open questions section when there are any.
Do not cite requirement numbers, since the requirements are not tracked.
Show code only for interfaces, schemas, and formats.
Say "the operator", not a person's name.

### tasks.md

```markdown
- [ ] 1. Add budget tables
  - Add the three ORM models and one Alembic migration.
  - Test that the migration runs up and down.
  - _Requirements: 3.1, 3.2_
```

- Each task can be reviewed and tested on its own, and builds on the ones before it.
- Each task cites the requirements it satisfies.
- Tests belong to the task that adds the behavior.
- Check tasks off as they land, and update the design when the build diverges.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
