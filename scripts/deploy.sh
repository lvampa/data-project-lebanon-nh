#!/usr/bin/env bash
# Build the static site and upload it to Cloudflare Pages. CI runs this on merge to main.
# By hand it ships the checkout as it is: bash scripts/deploy.sh [--dry-run]
# --dry-run builds, then stops before the upload.
#
# Auth comes from CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in CI, or from
# `wrangler login` on a laptop. CLOUDFLARE_PAGES_PROJECT is the Pages project name.
# NEXT_PUBLIC_DATA_URL, if set, is where the built site fetches its data.
set -euo pipefail

die() {
  echo "deploy: $1" >&2
  exit 1
}

[ -f scripts/deploy.sh ] && [ -d frontend/web ] || die "Run scripts/deploy.sh from the repo root."

case "$*" in
  "") dry_run=false ;;
  --dry-run) dry_run=true ;;
  *) die "unknown argument '$*'; the only option is --dry-run" ;;
esac
[ -n "${CLOUDFLARE_PAGES_PROJECT:-}" ] || die "CLOUDFLARE_PAGES_PROJECT is not set"

# The install and the build run code from the whole dependency tree, so they never get
# the Cloudflare credentials. Only the upload below does.
without_credentials() {
  env -u CLOUDFLARE_API_TOKEN -u CLOUDFLARE_ACCOUNT_ID "$@"
}

cd frontend
echo "→ Installing dependencies..."
without_credentials bun ci --ignore-scripts

cd web
echo "→ Building web..."
without_credentials bun run build

if $dry_run; then
  echo "✓ Dry run, not uploading."
  exit 0
fi

echo "→ Deploying to Cloudflare Pages..."
bun run wrangler pages deploy out --project-name "$CLOUDFLARE_PAGES_PROJECT" --branch=main

echo "✓ Done."
