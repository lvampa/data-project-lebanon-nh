#!/usr/bin/env bash
# Build the static site and upload it to Cloudflare Pages. CI runs this on merge to main,
# and it can be run by hand the same way: bash scripts/deploy.sh [--dry-run]
# --dry-run builds and checks the output, then stops before the upload.
#
# Auth comes from CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in CI, or from
# `wrangler login` on a laptop. Set CLOUDFLARE_PAGES_PROJECT to the Pages project name.
# NEXT_PUBLIC_DATA_URL, if set, is where the built site fetches its data.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
dry_run=false
[ "${1:-}" = "--dry-run" ] && dry_run=true

die() {
  echo "deploy: $1" >&2
  exit 1
}

# A hand run must ship what is on main, not whatever is checked out. CI is already
# on a tested main commit.
require_published_main() {
  [ "$(git -C "$REPO_ROOT" branch --show-current)" = main ] || die "not on main"
  [ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || die "the working tree is not clean"
  git -C "$REPO_ROOT" fetch --quiet origin main
  [ "$(git -C "$REPO_ROOT" rev-parse HEAD)" = "$(git -C "$REPO_ROOT" rev-parse origin/main)" ] ||
    die "HEAD is not origin/main"
}

# Next copies public/ into out/, and a local checkout has public/data. The site fetches its
# data in the browser, so none of it belongs in the build. Deleting out/data after the build
# leaves public/data alone, so a failed build cannot lose it.
remove_data_from_build() {
  rm -r -- "$REPO_ROOT/frontend/web/out/data" 2>/dev/null || true
}

# What is left in out/ is what gets published: no data and no dot folders.
check_build_output() {
  local stray
  stray=$(cd "$REPO_ROOT/frontend/web" && find out -name '.*' ! -name .well-known -o -path out/data)
  [ -z "$stray" ] || die "the build output contains data or a dot folder: $stray"
}

[ "${CI:-}" = true ] || require_published_main
[ -n "${CLOUDFLARE_PAGES_PROJECT:-}" ] || die "CLOUDFLARE_PAGES_PROJECT is not set"

cd "$REPO_ROOT/frontend"
bun ci

cd "$REPO_ROOT/frontend/web"
bun run build
remove_data_from_build
check_build_output

$dry_run && { echo "deploy: dry run, not uploading"; exit 0; }
bun run wrangler pages deploy out --project-name "$CLOUDFLARE_PAGES_PROJECT" --branch=main
