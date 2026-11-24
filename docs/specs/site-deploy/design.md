# Site deploy: design

**Status:** Draft
**Created:** 2026-11-23
**Updated:** 2026-11-23

## What it is

A hardened `scripts/deploy.sh` that publishes the public site to Cloudflare Pages from Connor's Mac, by hand or on a schedule.
CI stays checks-only and deploys nothing.
The database is on the Mac, and `next.config.ts` has `output: 'export'` with pages reading `public/data` at build time through `readDataFile`, so the export has to exist on disk when the build runs.
Today `deploy.sh` runs `generate_report.sh`, `bun run build`, then `wrangler pages deploy frontend/web/out --project-name=lebanon-pd-log --branch=main`, with no check between the steps.

## How it deploys

Wrangler direct upload only: `wrangler pages deploy`, and nothing else on Cloudflare.
Pages' Git integration is rejected, because the build needs data that is not in git and that Cloudflare cannot reach.
The Pages project must have no GitHub connection, or Cloudflare would build PR branches as previews on its own.
`wrangler` is pinned as a devDependency in `frontend/web`, which does not have it today, and `deploy.sh` runs it with `bunx`.
A direct upload is atomic per deployment: the site switches to the new one only when the upload finishes, and a failed upload leaves the last deployment live.

## Approaches

**A. Mac only. Recommended.**
Hardened `deploy.sh`, run by hand or by a scheduled job.
- Pro: no new secrets, no data leaves the Mac, nothing new to attack.
- Con: a code merge reaches the site only when the script next runs.

**B. Mac uploads an archive to a private R2 bucket, CI builds and deploys.**
Optional later step, and only worth it for redeploy-on-merge.
It needs R2 (a second Cloudflare product), two tokens, and a workflow that holds secrets.
If built: a `deploy.yml` in a `production` environment limited to `main`, a Pages-edit token and a read-only R2 token scoped to one bucket, `permissions: contents: read`, SHA-pinned actions, a `deploy` concurrency group, no `pull_request` trigger, and zizmor clean with no ignores.
Part A already leaves what B needs: the `manifest.json` below, and checks that need no database.
R2 is not used now.

**C. Code and data deployed apart, the page fetching data at runtime.**
Rejected for now.
Every page reads its data inside the build, so this means rewriting build-time pages into client fetches and designing a data host with CORS rules.
Revisit when the live API exists.

## Flow

```
scripts/deploy.sh
  1 take the lock                       one deploy at a time
  2 report-gen -> $TMPDIR/export        scan #1 and the location gate run inside report-gen
  3 check_export (Python)               scan #2 and every file check, on $TMPDIR/export
  4 swap into frontend/web/public/data
  5 bun install --frozen-lockfile --ignore-scripts, bun run build
  6 wrangler pages deploy out --project-name=<name> --branch=main
  7 smoke check the new deployment
```

Nothing replaces `public/data` until step 3 passes, so a failed run never leaves new and old files mixed.
Output is not verbose, and the scripts never print a matched string.

## Checks that block a deploy

In report-gen, so the exporter itself refuses to finish:
- The location pass is complete.
  It counts `address_normalizations` rows with `source = 'ai'` and a normalized address whose `prompt_version` does not start with the current `LOCATION_PROMPT_VERSION`, and exits non-zero if the count is above zero.
  The `startswith` covers the `+streets-...` suffix.
  Rule rows are not counted: they come from the street list, store `rules_prompt_version()` (`rules-3`) rather than a location version, and cannot name a person.
  A test covers a current AI row plus a current rule row passing, and one AI row on `location-1` failing.
  Until `normalize --field location --redo` covers every row, an unflagged row that names a person would publish in full, because only human rows fail closed.
  It prints the count only.
- Scan #1.
  After writing, it reads the `raw_address` and normalized text of rows with `names_person = true` and exits non-zero if any appears in the output.
  It skips a string equal to its own row's street and any string under 8 characters, so a short street name cannot match everything.
  It prints a count, never the text.
  Human rows are not scanned: they are flagged fail-closed, and many are businesses whose text legitimately appears under other spellings.

In `deploy.sh`, as an independent second check (`uv run python -m maintenance.check_export <dir>`):
- Scan #2, the same rule written separately in Python, so one bug cannot pass both.
- Every expected file exists and is non-empty: `stats.json`, `incidents.json`, `addresses.json`, `activity.json`, `staff.json`, `properties.json`, and `places/` with at least one file.
- The files agree: the place file count matches `addresses.json`; every pin id in `activity.json` is in `addresses.json`; and the activity entry count, `stats.mapped_total`, and the sum of `count` plus the sum of place `traffic_count` are all equal.
  The silent failure here is a pin the frontend drops without a word.
- Coverage, `mapped_total / total`, is at least 85%.
  It is 92.1% on dev today.

Any failure exits non-zero before the swap, the build or the upload.
A build failure also stops the run, and the site keeps its last deployment.

## The manifest

report-gen writes `manifest.json` into the export: an `export_version` integer and its git SHA.
Bump the version whenever an export field changes.
Nothing reads it in A.
B's workflow would refuse an archive older than the code expects, since a code merge can outrun the data, as #74 did with `nearby_traffic`.

## One deploy at a time

`deploy.sh` takes a lock with `mkdir "$REPO_ROOT/.deploy.lock"` and removes it in a `trap` on exit.
macOS has no `flock`.
A second run exits at once with a message.
A lock left by a killed run is removed by hand, and the message says which path.

## Smoke check

After the upload, `deploy.sh` reads the newest deployment's URL from `wrangler pages deployment list --project-name=<name> --json`.
It fetches `/` and `/data/stats.json` from that URL and fails if either is not a 200 or if `generated_at` differs from the local `stats.json`.
It checks the deployment's own URL, not the production domain, which may still serve a cached copy.
A failed smoke check does not roll back by itself; it exits non-zero and says to roll back.

## Rollback

Pages keeps every deployment.
List them with `bunx wrangler pages deployment list --project-name=<name>`.
To roll back, open the project's Deployments tab in the dashboard, pick the last good production deployment, and choose "Rollback to this deployment".
A bad export is fixed by fixing the cause and running `deploy.sh` again, which makes a new deployment.

## Freshness

`stats.json` carries `generated_at`, stamped by report-gen, and the site shows it as "Updated".
The smoke check proves the live copy is this run's.
`generate_report.sh` hard-codes `--since 2026-01-01`.
Deploy sets it to one year before today instead, which is the retention rule for the public site.
The data is only as fresh as the last run.

## Schedule and commands

By hand, from the repo root on the Mac:

```bash
bash scripts/deploy.sh
```

Scheduling is not built in step one.
The Airflow image has no `cargo`, `bun` or `wrangler`, no Cloudflare login, and no route to the Mac's files, so a `deploy_site` DAG could only SSH to the host.
That needs Remote Login and a private key mounted into the container, which is a bigger risk than the deploy it schedules.
The recommended scheduler is a launchd job on the Mac that runs the same command at 07:30 daily, after the 06:00 pipeline.
Whether to schedule at all is Connor's call.
Normalize and geocode run outside that chain, so the location gate is what stops a deploy that ran too early.

## Cloudflare Pages limits

Checked against the Cloudflare Pages docs (limits page and Direct Upload guide) on 2026-11-23:
- Free plan: 20,000 files per site and 25 MiB per file.
- Wrangler direct upload counts against 20,000; dashboard drag-and-drop caps at 1,000, so only Wrangler is used.
- Our `frontend/web/out` from the last local build has 1,709 files and 33 MB: 1,424 place files, and `properties.json` is the largest file at 2.6 MB.
  That is about 10 times headroom on files and 9 times on size.
  Watch the file count if it passes about 15,000.
- That `out` folder predates this branch; it is not a fresh build.

## Decisions

- **A over B.**
  B's only gain is redeploy on merge, and it costs R2, two tokens and a secret-holding workflow.
- **Two scans, in two languages.**
  A privacy bug in one implementation should not pass both.
- **Export to a temp dir, then swap.**
  Rejected: writing in place, which can leave a mix of old and new files for the next run to ship.
- **The scan covers `names_person` rows only.**
  Human rows would fail every deploy on legitimate business text.
- **A lock directory, not `flock`.**
  macOS does not ship `flock`.

## Open questions

- Keep the Pages project name `lebanon-pd-log`, or rename it?
  It predates a site that covers more than the police log, and a rename means a new project.
- Is 85% the right coverage floor?
- Schedule it with launchd (recommended), or keep it by hand?
