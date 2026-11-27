# Site deploy: design

**Status:** In progress
**Created:** 2026-11-23
**Updated:** 2026-11-24

## Overview

The site's code deploys from GitHub Actions to Cloudflare Pages when a commit lands on main.
The data is published separately, to a data host described below.
The build contains no data, so CI can build it.

The deploy is its own workflow, `.github/workflows/deploy.yml`, which runs when a push lands on main and touches `frontend/**`, `scripts/deploy.sh` or the workflow itself.
That push is its only trigger.
A redeploy is "Re-run all jobs" on the last run, and a deploy from another branch is a local `scripts/deploy.sh`.
Re-running an older run deploys that older commit over a newer one, so it is a rollback; the Pages Rollback in the Cloudflare dashboard is the intended way to do that.
A backend-only merge does not deploy.
It does not wait on `ci-ok`, since `ci.yml` is checks only.
It relies on `ci-ok` being a required check on pull requests, so nothing merges without passing, and the workflow fails on a broken build, so nothing broken ships.
The frontend job also runs `bun run build` on every PR, so a build break fails the PR and not main.
The deploy workflow runs `bash scripts/deploy.sh` and nothing else for the build and the upload, so a hand run and CI cannot drift.
The script runs `bun ci --ignore-scripts`, then `bun run build` in `frontend/web`, then `wrangler pages deploy out --branch=main`.
`--dry-run` stops before the upload.
There is no staging step and no smoke check: if the build passes, it ships.
`scripts/deploy.sh` replaces the old hand-run script, which uploaded a build with data in it and ran no checks.
A hand run ships whatever is checked out, on any branch, with local changes and ignored files such as a `.env.local`.
That is the operator's call, and CI is the path that builds a clean checkout of main.
The script makes no git calls, runs from the repo root with paths relative to it, and exits with a message if it is run from anywhere else.
It reads `CLOUDFLARE_PAGES_PROJECT`, and auth comes from `wrangler login` locally or the token in CI.

## Data in the browser

Four pages used to read the export while building: incidents, properties, public safety and staff.
They now fetch their JSON in the browser through `useDataFile`, and show a loading state, then an error with a Try again button.
The two fetches that already ran in the browser, `activity.json` and each place card, use the same base through `fetchDataFile`, and a place card is read with `useDataFile`.
`useDataFile` fetches each file once per page load, so moving between pages does not download it again.
`activity.json` goes through the same cache, and a place card is not cached, so its fetch is aborted when another pin is chosen.

The base is `NEXT_PUBLIC_DATA_URL`, and it defaults to `/data`.
`NEXT_PUBLIC_DATA_URL` is read when the build runs, so pointing the site at a data host means a rebuild.
In CI it comes from the repository variable of the same name, and an empty value counts as unset.
A deployed build with nothing at the data URL shows the error state on those four pages.

## Publishing the data

The data side has its own script, `scripts/deploy-data.sh`, run from the repo root like `deploy.sh`.
It takes `--dry-run`, which stops before the upload.
1. It runs `uv run privacy-holds mark`, which holds unsafe person locations (below).
2. It runs `generate_report.sh`, which writes the export to `data/export/` at the repo root, outside `public/`, so it never reaches the build.
3. It runs `uv run check-export data/export`, and nothing uploads unless every check passes.
4. It runs `aws s3 sync data/export s3://$R2_BUCKET/ --delete` against R2's S3 endpoint, with `application/json` and `Cache-Control: public, max-age=300`.

It is a plain sync of the folder.
There are no versioned releases, no pointer file and no schema version.
`--delete` removes a place card that is gone, and the bucket holds only this export.
`aws` is already on the operator's Mac, and one sync command handles about 1,500 files.
The script needs `R2_BUCKET`, an endpoint, and credentials, and fails before the export when any is missing:
- The endpoint is `R2_ENDPOINT`, or `https://$CLOUDFLARE_ACCOUNT_ID.r2.cloudflarestorage.com`.
- The credentials are `AWS_PROFILE`, an aws CLI profile made with `aws configure --profile <name>`, for a hand run on the operator's Mac.
  Or they are `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, which Airflow's task sets.
  Both forms together are refused, and an empty value or the text `None` counts as not set.
- Everything before the upload (`privacy-holds mark`, the export and `check-export`) runs without the three credential variables, so only the `aws` call sees them.
- Before `sync --delete` it prints the bucket and the endpoint host, so a wrong target shows in the log.
The script prints nothing from the environment, never turns on tracing, and uses no aws debug flag.
R2 rejects the checksum headers newer `aws` versions add, so the script sets `AWS_REQUEST_CHECKSUM_CALCULATION` and `AWS_RESPONSE_CHECKSUM_VALIDATION` to `when_required`.

### Privacy holds

A location the AI flagged as naming a person is published as its street only.
When it is unclear that this is enough, the publish does not fail: the location is held out and listed for a person to handle.
- `address_normalizations` has `privacy_hold`, `privacy_handled_at` and `privacy_handled_text`, from one migration.
  A row is held while `privacy_hold` is true and `privacy_handled_at` is null.
- The public views `public_locations` and `public_log_entries` treat a held location as unmapped: no name, no street, no pin, and no place card.
  Its log entries stay, with no location, and count in the totals.
  This is in the views, so report-gen is unchanged.
- `privacy-holds mark` holds every flagged location that is not clearly safe, and never clears a hold.
  A flagged location is clearly safe only when its normalized text is a plain address: a house number and a street, or a street, from the street list the AI was given (`load_street_list`).
  Otherwise `mark` holds every row with that normalized text, flagged or not, since an unflagged twin could carry the same name.
  The view never publishes a flagged row's raw text, so that text cannot reach the export.
  One small function, `is_clearly_safe`, holds the rule.
- `handled` remembers the text it released in `privacy_handled_text`.
  If `normalize` later rewrites the text, `mark` holds the row again.
- `privacy-holds list` prints the id, kind and raw text of each held location, for the operator's terminal only.
  `privacy-holds handled <id>...` sets `privacy_handled_at`, and the location then publishes as any flagged location does.
  Moving this into the admin app is later work.
- The migration and `mark` write to the database, so the operator runs `uv run migrate` before the first publish.

The checks are in `scripts/check_export.py`, and they fail closed and print counts, never the matched text:
- **Person text.** No flagged location's text appears in the export.
  A flagged row's raw text must not appear at all.
  Its normalized text may appear only when it is a plain address or street, or when every row with that text has been handled.
  A held row is checked the same way.
  It reads the parsed string values, so a name written with a JSON escape is still found.
  A flagged row's own street is skipped, and so is any text under 8 characters, because a short street name would match half the export.
  That means this check is not fail-closed for a short text.
  `properties.json` and `staff.json` are not scanned, since a parcel's address may be the same text.
  This is the guard after the holds: it fails closed if anything slips through.
- **Prompt version.** No AI location is on a prompt older than `MIN_PRIVACY_LOCATION_PROMPT`, the first one that flags a person.
  The number is parsed from `location-<n>+streets-<hash>`, since the street suffix varies.
  Later prompts changed matching, not privacy, so the current version is not required.
  Rule rows are not counted, since they store their own version.
- **Links.** Every `source_url` and `detail_url` is `https` on `www.lebanonnh.gov`, `lebanonnh.gov` or `gis.vgsi.com`.
- **Coverage.** At least 85% of in-range entries sit on a pin.
- **Files.** Every expected file is present, and every pin in `addresses.json` has a card in `places/`.

An export version that the build checks is not built, so new code can read old data without any check.

The Airflow `publish_data` DAG runs `bash scripts/deploy-data.sh` as its one task, so the script stays the single entrypoint.
It is manual only: normalizing and geocoding run outside the police-log chain, so no clock time is right, and the prompt-version check refuses an export that ran too early.
The Airflow image gets what the script needs:
- A multi-stage build compiles `report-gen` on `rust:1.100.0-bookworm` and copies the binary in, and `REPORT_GEN_BIN` points `generate_report.sh` at it, so the image has no Rust toolchain.
- The aws CLI v2, installed from AWS's zip at a pinned version, which is a bundled binary and cannot clash with the boto packages Airflow pins.
The R2 credentials are an Airflow Connection, `r2_data`, not container environment and not a mounted file:
- It is an `aws` Connection. The login is the R2 access key id and the password is its secret.
  The extras are `{"endpoint_url": "https://<account_id>.r2.cloudflarestorage.com", "region_name": "auto", "bucket": "<bucket>"}`.
  The bucket name is not secret, so it lives in the extras and there is no Variable.
- `publish_data` is a Python task. When it runs, it reads the Connection with `BaseHook.get_connection("r2_data")` and runs `uv run --frozen bash scripts/deploy-data.sh` as a subprocess, with `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `R2_ENDPOINT` and `R2_BUCKET` in that subprocess's environment only (`dags/publish.py`).
  The worker's own environment is not changed, no other task gets them, and `compose.yml` has no R2 variable and no `~/.aws` mount.
- The task logs the script's output line by line.
  The script prints no credential, and an error about a missing Connection field names the field, not its value.
- Airflow hides a Connection password in its logs.
  That masking is not tested here, and neither is the Python task itself, since Airflow is not installed in the test environment.

The DAG's task fails until the Connection exists.
The image build is not tested here.

R2 needs these set in Cloudflare, by the operator:
- A bucket on a custom subdomain of a domain already on Cloudflare.
  `r2.dev` is rate-limited and for development only.
- An API token, made under R2, Manage API tokens, with Object Read & Write on that one bucket only and an expiry.
  Add an IP filter only if the host's address is stable.
- A CORS rule allowing GET from the site's origin, or every fetch fails and the pages show the error state.
- A Cache Rule that makes the data host cacheable, since Cloudflare does not cache `.json` by default.

For local dev, `bun run dev` is plain `next dev`, and there is no data server.
Without `NEXT_PUBLIC_DATA_URL`, the four data pages show the error state, because nothing serves `/data`.
To see data, set `NEXT_PUBLIC_DATA_URL` to the R2 subdomain in `frontend/web/.env.local`, which is gitignored.
To look at a fresh export, run `deploy-data.sh --dry-run` and read the files in `data/export/`.

### Adding the Connection

Create it once in the Airflow UI, under Admin, Connections, so the secret is never on a command line or in shell history:
- Connection Id `r2_data`, Connection Type `Amazon Web Services`.
- AWS Access Key ID: the R2 token's access key id.
- AWS Secret Access Key: the token's secret.
- Extra: `{"endpoint_url": "https://<account_id>.r2.cloudflarestorage.com", "region_name": "auto", "bucket": "<bucket>"}`.

Safety notes:
- The token is scoped to one bucket, so a leaked key can write that bucket and nothing else.
- The keys are in the task's environment only, and not in the image, the compose file or a mounted folder.
- A bad write is recovered by running the publish again, since it syncs the whole export.

### Links in the data

Three fields from the data are used as a link target: `source_url` (the incidents table and a call row), `detail_url` (a parcel's VGSI link) and `person.email` (a `mailto:`).
There is no `dangerouslySetInnerHTML` and no data-driven `src`.
React 19 blocks a `javascript:` URL in an `href`.
Every link that opens a new tab sets `rel="noopener noreferrer"`.
`check-export` fails the publish if a `source_url` or `detail_url` is not `https` on the city's log host or VGSI, so swapped data cannot point a link elsewhere.
`person.email` is in `staff.json`, which is empty today, and is not validated.

## Deploy hardening

The repo is public, so the workflow is narrow:
- The workflow runs only on a push to main.
  There is no `pull_request` or `pull_request_target` path to it.
- It runs in the `production` environment, which is limited to the main branch in the repository settings.
  The API token is a secret of that environment, so a branch cannot read it.
- `permissions: contents: read`, and every action is pinned by SHA.
- Wrangler is a devDependency of `frontend/web` at `~4.168`, and the lockfile fixes the exact version that `bun ci` installs, failing on a stale lockfile.
  Both CI installs and the script use `bun ci --ignore-scripts`.
  Bun runs the install scripts of packages on its built-in default trust list unless told not to, so the flag is what keeps them off.
- The deploy workflow has only the `push` trigger, and its own file, so a trigger added to `ci.yml` later cannot deploy by accident.
- The `deploy` concurrency group queues a second deploy instead of cancelling one that is uploading.
- `public/` is copied into `out` as is, and the script does not check what is in it.
  The export is not under `public/`, so a clean checkout has no data there.
  A leftover `frontend/web/public/data` from the old export location would be uploaded by a hand run, so delete that folder.

Pages is used as a direct upload only, with no GitHub connection on the Cloudflare project.
Otherwise Cloudflare would build pull request branches on its own.

Repository settings, set by the operator:
- Secret `CLOUDFLARE_API_TOKEN`, in the `production` environment, with the Cloudflare Pages: Edit permission only.
- Variable `CLOUDFLARE_ACCOUNT_ID`.
- Variable `CLOUDFLARE_PAGES_PROJECT`, the name of the Pages project.
- Branch protection on main: `ci-ok` required, "Require branches to be up to date before merging" on, and direct pushes blocked with no admin bypass.
  The deploy workflow does not wait on `ci-ok`, so these settings are what stop untested code from shipping.
  A push that bypasses them deploys whatever it contains, and the script catches a broken build but not a failing test.
- The `production` environment limited to the main branch.
- Variable `NEXT_PUBLIC_DATA_URL`, the data subdomain, once the bucket exists.
- For `deploy-data.sh`, the R2 bucket, its custom subdomain, the R2 API token, the CORS rule and the Cache Rule above.
- For `deploy-data.sh` by hand: `R2_BUCKET`, `CLOUDFLARE_ACCOUNT_ID` (or `R2_ENDPOINT`) and an aws profile in `AWS_PROFILE`.
- For the Airflow DAG: the `r2_data` Connection above.

## Decisions

- **A separate `deploy.yml` on push, not a job in `ci.yml` or a `workflow_run` workflow.**
  `ci.yml` stays checks only, and a deploy-only file is easy to audit.
  A path filter skips backend-only merges.
  Rejected: `workflow_run`, which runs against the default branch's latest commit and is a trigger that zizmor flags as dangerous.
  Rejected: `needs: ci-ok` in the same file, which ties the deploy to every check, including the ones a frontend deploy does not depend on.
  The cost is that nothing in the workflow proves the checks passed, so `ci-ok` has to stay required in branch protection.
- **One script for CI and hand runs.**
  Rejected: a workflow with its own build and upload steps, which would drift from what a person runs.
  The token is in the step's environment, but the script runs the install and the build without the Cloudflare variables, so only the Wrangler line sees them.
  The build runs code from the whole dependency tree, and any package could read the environment.
  Something that tampers with files on the same runner could still reach the token.
- **Fetch in the browser, not at build time.**
  CI has no database and no export, so a build that needs data cannot run there.
  Cost: the four lists are not in the page HTML, so a crawler that does not run JavaScript sees a loading state.
- **Wrangler at `~4.168`, in the lockfile, not `bunx wrangler@x`.**
  The range is the operator's choice, so patch releases of 4.168 are accepted, and the lockfile fixes the one that installs.
  Pinning only wrangler would let its dependencies resolve fresh on each run.
  Bump the version by hand.
- **No staging, no smoke check.**
  Pages keeps every deployment, so a bad one is undone with Rollback in the Cloudflare dashboard or the rollback API.
  The site is a hobby site and the checks run first.

## Cost

Everything stays on free tiers: Pages free, the R2 free tier, and GitHub Actions on a public repo.
Pages Free allows 500 builds a month, and the plan is fewer than 5 deploys a month.

## Cloudflare Pages limits

Checked against the Cloudflare docs on 2026-11-24:
- Free plan: 20,000 files per site and 25 MiB per file.
- A build with no data is under 100 files, so the limits matter only if the data ever goes back into the build.
- Free Functions requests are not used.

## Open questions

- How the data gets into the bucket, for example from an Airflow job.
  Until it does, the deployed site has no data.
- Whether the Pages project keeps the name `lebanon-pd-log`.
