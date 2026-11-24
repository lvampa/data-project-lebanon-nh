# Site deploy: design

**Status:** Draft
**Created:** 2026-11-23
**Updated:** 2026-11-23

## What it is

A way to put the public site on Cloudflare Pages without anyone typing `wrangler` by hand.
The database stays on Connor's Mac, so only the Mac can export.
CI builds and deploys from an export the Mac uploaded, and never touches Postgres.
Today `scripts/deploy.sh` does everything on the Mac: `generate_report.sh`, `bun run build`, then `wrangler pages deploy frontend/web/out --project-name=lebanon-pd-log --branch=main`.
`next.config.ts` has `output: 'export'`, and pages read `public/data` at build time through `readDataFile`, so the data has to be on disk when the build runs.

## How it deploys

Wrangler direct upload only: `wrangler pages deploy`, and nothing else on Cloudflare.
Pages' Git integration is rejected, because the build needs data that is not in git and that Cloudflare cannot reach.
In CI the step is `bunx wrangler pages deploy out --project-name=<name> --branch=main`, run from `frontend/web`.
`wrangler` is pinned as a devDependency in `frontend/web`, which does not have it today, so CI and the Mac run the same version.

## Approaches

**A. Mac only.**
Harden `deploy.sh` with the checks below and run it by hand, or from an Airflow DAG after the daily pipeline.
CI deploys nothing.
- Pro: no new secrets, no data leaves the Mac, nothing new to secure.
- Con: a code merge does not reach the site until Connor runs the script, and the Mac needs a Cloudflare login.
- Con: an Airflow DAG would have to run `cargo`, `bun` and `wrangler` inside the Airflow image, which has none of them.

**B. Mac exports and uploads, CI builds and deploys.**
The Mac runs the export and the checks, then uploads one archive to a private R2 bucket.
A `deploy` workflow downloads it, builds, and deploys with a Pages-only token.
It runs on `workflow_dispatch` (the Mac triggers it after an upload) and on a push to `main` (a code merge redeploys with the last data).
- Pro: this is the goal: CI deploys, with a script that runs it, and merges reach the site on their own.
- Con: a second Cloudflare product (R2, free tier covers about 12 MB), two tokens, and one workflow that holds secrets.

**C. Code and data deployed apart, the page fetching data at runtime.**
Rejected for now.
Every page reads its data inside the build, so this means rewriting pages that render at build time into client fetches, and designing a data host and its CORS rules.
It also gives up the static, fast pages.
Revisit when the live API exists.

**Recommendation: B, built in two steps.**
Step one is A, which is useful alone: the checks and a hardened `deploy.sh`, and it covers every privacy check.
Step two adds the upload and the workflow, and `deploy.sh` stays as the fallback when CI or R2 is down.
Step two only buys a code merge that redeploys itself, so it is Connor's explicit choice after step one, not the default plan.

## Data flow (B)

```
Mac   scripts/publish_data.sh
        generate_report.sh        --since is today minus one year
        scripts/check_export.sh   blocks on any failed check
        tar the data dir  ->  wrangler r2 object put site-data/export.tar.gz
        gh workflow run deploy.yml
CI    deploy.yml (environment: production)
        checkout, bun install --frozen-lockfile
        download export.tar.gz with a read-only R2 token, unpack into frontend/web/public/data
        sanity checks, bun run build, wrangler pages deploy
```

The archive holds only what report-gen wrote, which reads the two `public_*` views.
It still sits in a private bucket and is never a workflow artifact, a cache entry, or a log line.

## Checks that block a deploy

`publish_data.sh` exports into a fresh `$TMPDIR` folder and checks it there.
It replaces `frontend/web/public/data` only after every check passes, so a failed run never leaves new and old files mixed for the `deploy.sh` fallback to ship.

On the Mac, in `check_export.sh`, before any upload:
- report-gen exits non-zero.
- The location pass is complete.
  The check counts `address_normalizations` rows from the AI or rules with a normalized address whose `prompt_version` does not start with the current `LOCATION_PROMPT_VERSION`, and fails if the count is above zero.
  Until `normalize --field location --redo` covers every row, an unflagged row that names a person would publish in full, because only human rows fail closed.
  It prints the count only.
- Every expected file exists and is non-empty: `stats.json`, `incidents.json`, `addresses.json`, `activity.json`, `staff.json`, `properties.json`, and `places/` with at least one file.
- The files agree with each other, which needs no database, so CI runs these too:
  the place file count matches `addresses.json`;
  every pin id in `activity.json` is in `addresses.json`;
  the activity entry count equals `stats.mapped_total`;
  and the sum of `count` plus the sum of place `traffic_count` equals `mapped_total`.
- The coverage line stays at or above 85%.
  It is `mapped_total / total` from `stats.json`, which is 92.1% on dev today.
- A person-text scan, which #70 asks for.
  It reads the `raw_address` and normalized text of rows with `names_person = true` and fails if any appears in an export file.
  It skips strings equal to their own `street` and strings under 8 characters, so a short street name cannot match everything.
  Human rows are not scanned: they are flagged fail-closed, and many are businesses whose text legitimately appears under other spellings.
  It prints the count and the file names, never the strings.
  It needs the database, so it only runs on the Mac.

In CI, before the build:
- The no-database checks above, in case the upload was partial.
- The export version check: the archive carries a `manifest.json` with an export version, and the workflow fails, with Pages unchanged, when the code expects a newer one.
  The version is bumped whenever an export field changes, since a code merge can outrun the archive, as #74 did with `nearby_traffic`.
- The build itself.
  A failed build fails the job, and Pages keeps serving the last deployment.

## Secrets and permissions

- `CLOUDFLARE_API_TOKEN` is an API token with one permission: Account, Cloudflare Pages, Edit.
  It cannot touch R2, DNS, or other projects.
- `R2_READ_*` is an R2 token scoped to the one bucket, read only.
  The Mac holds the write token in its own environment, never in GitHub.
- Both live in a GitHub environment named `production`, limited to the `main` branch.
  Required reviewers are not used: Connor is the only maintainer, and a self-approval gate would only block the unattended redeploy.
  Fork PRs get no secrets, since the workflow has no `pull_request` trigger.
- The workflow sets `permissions: contents: read`, checks out with `persist-credentials: false`, pins every action to a SHA like `ci.yml`, and passes secrets through `env` on the one step that needs each, never inline in `run`.
- The workflow sets `concurrency: { group: deploy, cancel-in-progress: false }`, so a dispatch and a push cannot deploy over each other.
- `bun install --frozen-lockfile --ignore-scripts`, if the build needs no lifecycle scripts, since dependencies run in a job that later holds the Pages token.
- No `tar -v` and no verbose wrangler output, to keep logs tidy.
- The Pages project must be Direct Upload with no GitHub integration, or Cloudflare builds PR branches as previews by itself.
- `workflow_dispatch` is the only input path and takes no inputs, so there is nothing to inject.
- `zizmor.yml` already audits `.github/**`.
  The new workflow must pass it with no ignores; a finding is fixed or the step is redesigned, not suppressed.
- `CLOUDFLARE_ACCOUNT_ID` is a secret in the same environment, next to the token.
- The project name is a repository variable.

## PR previews

Not done.
Pages previews would need a build, and the only data that exists is real.
CI's existing `frontend` job already typechecks and tests pages against fixtures.
If previews are wanted later, they build from a committed fixture folder and never from R2.

## Rollback

Pages keeps every deployment.
To roll back, open the project's Deployments tab, pick the last good production deployment, and choose "Rollback to this deployment", or redeploy an older build from the dashboard.
A bad export is also fixed by re-running `publish_data.sh` after the fix, which replaces the archive and redeploys.
Because the push-to-`main` trigger reuses the uploaded archive, a bad archive keeps redeploying until it is replaced.
`check_export.sh` is what keeps a bad one from being uploaded.

## Freshness

`stats.json` carries `generated_at`, stamped by report-gen.
A merge-only redeploy reuses the old archive, so the site's "Updated" date keeps showing when the data was exported, which is the true answer.
The window start is computed by `publish_data.sh` as one year before today, replacing the fixed `2026-01-01` in `generate_report.sh`, so the public site shows the last year as the retention decision says.
Data is only as fresh as the last time Connor ran the script.

## Who runs what

- By hand, after the daily pipeline settles: `bash scripts/publish_data.sh`.
- Automatic: a push to `main` redeploys with the last archive.
- Not scheduled in step one.
  An Airflow task cannot run the script, since the image has no `cargo`, `bun` or `wrangler`.
  A launchd job on the Mac is the way to schedule it later.

## Cloudflare Pages limits

Verified against the Cloudflare Pages docs (limits page, Direct Upload guide) on 2026-11-23:
- Free plan: 20,000 files per site, and 25 MiB per file.
  Wrangler uploads count against 20,000; dashboard drag-and-drop caps at 1,000, so only Wrangler is used.
- Our `frontend/web/out` from the last local build has 1,709 files and 33 MB.
  1,424 of them under `data/` are the place files and the largest file is `properties.json` at 2.6 MB.
- That leaves about 10 times headroom on files and 9 times on size.
  Place files grow with places on the map, so watch the file count if it passes about 15,000.
- The out folder is from an earlier build in the worktree, not a fresh one from this branch.

## Decisions

- **Stale project name.**
  `lebanon-pd-log` predates the site covering more than the police log.
  Whether to rename it is Connor's; a rename means a new Pages project and a new domain setting, so the spec keeps the name in a repository variable.
- **R2 over a GitHub release or artifact.**
  The repo is public, so a release or artifact is public too.
  R2 is private and free at this size.
- **The scan runs on the Mac.**
  It needs the database, and the flagged strings must never reach CI.

## Open questions

- B stores the export in R2, which is a second Cloudflare product, and Connor wants only Pages.
  If R2 is out, B has no private place for the archive, and A is the recommendation.
- Keep the project name, or rename?
- Is 85% the right coverage floor?
- Should a push-to-`main` redeploy refuse archives older than some number of days?
