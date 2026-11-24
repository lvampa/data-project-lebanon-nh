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
A backend-only merge does not deploy.
It does not wait on `ci-ok`, since `ci.yml` is checks only.
It relies on `ci-ok` being a required check on pull requests, so nothing merges without passing, and the workflow fails on a broken build, so nothing broken ships.
The frontend job also runs `scripts/deploy.sh --dry-run` on every PR, against a planted data file, so a build break or a broken data guard fails the PR and not main.
The deploy workflow runs `bash scripts/deploy.sh` and nothing else for the build and the upload, so a hand run and CI cannot drift.
The script runs `bun ci --ignore-scripts`, then `bun run build` in `frontend/web`, then checks `out`, then `wrangler pages deploy out --branch=main`.
`--dry-run` stops before the upload.
There is no staging step and no smoke check: if the build passes, it ships.
`scripts/deploy.sh` replaces the old hand-run script, which uploaded a build with data in it and ran no checks.
A hand run ships whatever is checked out, on any branch, with local changes and ignored files such as a `.env.local`.
It prints the branch, the short SHA and whether the tree is dirty before it uploads, and does not stop.
That is the operator's call, and CI is the path that builds a clean checkout of main.
It reads `CLOUDFLARE_PAGES_PROJECT`, and auth comes from `wrangler login` locally or the token in CI.

## Data in the browser

Four pages used to read `public/data` while building: incidents, properties, public safety and staff.
They now fetch their JSON in the browser through `useDataFile`, and show a loading state, then an error with a Try again button.
The two fetches that already ran in the browser, `activity.json` and each place card, use the same base through `fetchDataFile`, and a place card is read with `useDataFile`.
`useDataFile` fetches each file once per page load, so moving between pages does not download it again.
`activity.json` goes through the same cache, and a place card is not cached, so its fetch is aborted when another pin is chosen.

The base is `NEXT_PUBLIC_DATA_URL`, and it defaults to `/data`.
Local dev and `generate_report.sh` are unchanged: the export still lands in `public/data` and Next serves it.
A deployed build with no data at `/data` shows the error state on those four pages.
`NEXT_PUBLIC_DATA_URL` is read when the build runs, so pointing the site at a data host means a rebuild.
In CI it comes from the repository variable of the same name, and an empty value counts as unset.

The planned data host is a public R2 bucket on a subdomain of a domain already on Cloudflare, with a Cache Rule so the JSON is cached at the edge.
Cloudflare does not cache `.json` by default, and `r2.dev` is rate-limited and for development only, so the custom domain and the rule are both needed.
Publishing the data is a later change.
The bucket needs a CORS policy that allows GET from the site's origin, or every fetch fails and the pages show the error state.
Once the host exists, the operator sets the repository variable to its URL.

Nothing publishes data in this change, and it must not reach the public host until the publish step runs the privacy checks.
Those are the location-pass check, a scan that no flagged person name appears in the export, and a check that the files agree with each other.
The old design had them, and they move with the publish step.
A data version in the export, checked by the build, is also part of that step.
Until it exists, new code can read old data without any check.

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
- `public/` is copied into `out` as is, and a local checkout has `public/data`.
  The script deletes `out/data` after the build and then fails if `out` has a `data` folder or any dot entry except `.well-known`.
  Deleting from `out` leaves `public/data` alone, so even a failed build cannot lose the local data.
  Rejected: moving `public/data` aside and restoring it, which risks the data if the script is killed.

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
- Variable `NEXT_PUBLIC_DATA_URL`, later, once the data host exists.

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
