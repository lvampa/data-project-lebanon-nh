#!/usr/bin/env bash
# Build the static site and upload it to Cloudflare Pages. CI runs this on merge to main.
# By hand it ships whatever is checked out: bash scripts/deploy.sh [--dry-run]
# --dry-run builds and checks the output, then stops before the upload.
#
# Auth comes from CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in CI, or from
# `wrangler login` on a laptop. CLOUDFLARE_PAGES_PROJECT is the Pages project name.
# NEXT_PUBLIC_DATA_URL, if set, is where the built site fetches its data.
set -euo pipefail

die() {
  echo "deploy: $1" >&2
  exit 1
}

case "${1:-}" in
  "") dry_run=false ;;
  --dry-run) dry_run=true ;;
  *) die "unknown argument '$1'; the only option is --dry-run" ;;
esac
[ "$#" -le 1 ] || die "too many arguments"
[ -n "${CLOUDFLARE_PAGES_PROJECT:-}" ] || die "CLOUDFLARE_PAGES_PROJECT is not set"

# The install and the build run code from the whole dependency tree, so they never get
# the Cloudflare credentials. Only the upload below does.
without_credentials() {
  env -u CLOUDFLARE_API_TOKEN -u CLOUDFLARE_ACCOUNT_ID "$@"
}

cd "$(dirname "$0")/../frontend"
echo "→ Installing dependencies..."
without_credentials bun ci --ignore-scripts

cd web
echo "→ Building web..."
without_credentials bun run build

# Next copies public/ into out/, and a local checkout has public/data. The site fetches its
# data in the browser, so none of it belongs in the build. Deleting from out/ leaves
# public/data alone, so even a failed build cannot lose it.
echo "→ Checking the build has no data..."
rm -r -- out/data 2>/dev/null || true

# What is left in out/ is what gets published: no data and no dot folders.
stray=$(find out -name '.*' ! -name .well-known -o -path out/data)
[ -z "$stray" ] || die "the build output contains data or a dot folder: $stray"

if $dry_run; then
  echo "✓ Dry run, not uploading."
  exit 0
fi

echo "→ Deploying to Cloudflare Pages..."
bun run wrangler pages deploy out --project-name "$CLOUDFLARE_PAGES_PROJECT" --branch=main

echo "✓ Done."
