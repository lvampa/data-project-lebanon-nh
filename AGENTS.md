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
- Spider tests use `scrapy.http.HtmlResponse` / `TextResponse` to build fake responses, with no live HTTP
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
- Read `docs/frontend/brand.md` before changing styles, the header, the footer, or charts.
- Use the tokens in `frontend/shared/styles/` (`text-display-*`, `eyebrow`, color names) instead of arbitrary values like `text-[34px]`.
- Run `bun run check` from `frontend/` before pushing; the pre-push hook runs it too.

## 8. Specs and plans

Specs are for project features and are tracked in the repo.
Implementation plans are for you, and are not.

- Write the spec before coding the feature.
- Save implementation plans to `.claude/plans/YYYY-MM-DD-<name>.md`, which is not tracked.
- Delete a plan once it is implemented, after updating the feature's spec to match what was built.

### Spec layout

Each feature gets `docs/specs/<feature-name>/` with a short kebab-case name and three files, written and reviewed in order:

1. `requirements.md`: what the feature must do and why.
2. `design.md`: how it will be built.
3. `tasks.md`: the design broken into steps that can be checked off.

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
- Number criteria `<requirement>.<criterion>`, like `2.3`, so design and tasks can cite them.
- Requirements describe observable behavior; implementation choices go in the design.

### design.md

Sections, skipping any that do not apply: Overview (with the requirements it covers), Architecture, Components and interfaces, Data models, Error handling, Testing strategy, Decisions (with rejected alternatives and why), Open questions.
Show code only for interfaces, schemas, and formats.

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
