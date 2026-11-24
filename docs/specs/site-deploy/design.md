# Site deploy: design

**Status:** In progress
**Created:** 2026-11-23
**Updated:** 2026-11-24

## Overview

The site's code deploys from GitHub Actions to Cloudflare Pages when a commit lands on main.
The data is published separately, to a data host described below.
The build contains no data, so CI can build it.

The deploy is the `deploy` job in `.github/workflows/ci.yml`.
It needs `ci-ok`, so it runs only after every check passed on that commit.
The frontend job also runs `bun run build` on every PR, so a build break fails the PR and not main.
The deploy job runs `bun install --frozen-lockfile --ignore-scripts` and `bun run build` in `frontend/web`, then `wrangler pages deploy out --branch=main`.
There is no staging step and no smoke check: if the build passes, it ships.

## Data in the browser

Four pages used to read `public/data` while building: incidents, properties, public safety and staff.
They now fetch their JSON in the browser through `useDataFile`, and show a loading state, then an error with a Try again button.
The two fetches that already ran in the browser, `activity.json` and each place card, use the same base.

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
- The job runs only on a push to main or a manual run of the workflow on main.
  There is no `pull_request` or `pull_request_target` path to it.
- It runs in the `production` environment, which is limited to the main branch in the repository settings.
  The API token is a secret of that environment, so a branch cannot read it.
- `permissions: contents: read`, and every action is pinned by SHA.
- Wrangler is a pinned devDependency of `frontend/web`, installed from the lockfile with `--ignore-scripts`, so the step that holds the token runs only locked code.
- The `deploy` concurrency group queues a second deploy instead of cancelling one that is uploading.
- The job fails if `out` has a `data` folder or any dot entry except `.well-known`.
  `public/` is copied into `out` as is, so this keeps data and stray folders out of what is published.

Pages is used as a direct upload only, with no GitHub connection on the Cloudflare project.
Otherwise Cloudflare would build pull request branches on its own.

Repository settings, set by the operator:
- Secret `CLOUDFLARE_API_TOKEN`, in the `production` environment, with the Cloudflare Pages: Edit permission only.
- Variable `CLOUDFLARE_ACCOUNT_ID`.
- Variable `CLOUDFLARE_PAGES_PROJECT`, the name of the Pages project.
- Variable `NEXT_PUBLIC_DATA_URL`, later, once the data host exists.

## Decisions

- **A job in `ci.yml`, not a `workflow_run` workflow.**
  The job deploys the commit the checks just passed on.
  `workflow_run` runs against the default branch's latest commit and is a trigger that zizmor flags as dangerous.
  Rejected: a separate `deploy.yml`.
- **Fetch in the browser, not at build time.**
  CI has no database and no export, so a build that needs data cannot run there.
  Cost: the four lists are not in the page HTML, so a crawler that does not run JavaScript sees a loading state.
- **Wrangler in the lockfile, not `bunx wrangler@x`.**
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
