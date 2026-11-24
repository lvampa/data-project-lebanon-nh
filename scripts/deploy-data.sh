#!/usr/bin/env bash
# Export the report data, check it, and sync it to the R2 bucket the site reads from.
# From the repo root: bash scripts/deploy-data.sh [--dry-run]
# --dry-run exports and checks, then stops before the upload.
#
# The upload needs R2_BUCKET, CLOUDFLARE_ACCOUNT_ID, AWS_ACCESS_KEY_ID and
# AWS_SECRET_ACCESS_KEY, the last two from an R2 API token with Object Read & Write on
# that one bucket. They come from the environment only.
set -euo pipefail

die() {
  echo "deploy-data: $1" >&2
  exit 1
}

[ -f scripts/deploy-data.sh ] && [ -d frontend/web ] || die "Run scripts/deploy-data.sh from the repo root."

case "$*" in
  "") dry_run=false ;;
  --dry-run) dry_run=true ;;
  *) die "unknown argument '$*'; the only option is --dry-run" ;;
esac

# Fail before the slow export, not after it.
if ! $dry_run; then
  for name in R2_BUCKET CLOUDFLARE_ACCOUNT_ID AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY; do
    [ -n "${!name:-}" ] || die "$name is not set"
  done
fi

echo "→ Exporting the report data..."
bash scripts/generate_report.sh

# Nothing is uploaded unless every check passes. The checks print counts, never the text.
echo "→ Checking the export..."
uv run check-export data/export

if $dry_run; then
  echo "✓ Dry run, not uploading."
  exit 0
fi

# R2 rejects the checksum headers that newer aws versions add by default.
export AWS_REQUEST_CHECKSUM_CALCULATION=when_required
export AWS_RESPONSE_CHECKSUM_VALIDATION=when_required

# --delete drops a place card that is gone. The bucket holds only this export.
echo "→ Uploading to R2..."
aws s3 sync data/export "s3://$R2_BUCKET/" \
  --delete \
  --region auto \
  --endpoint-url "https://$CLOUDFLARE_ACCOUNT_ID.r2.cloudflarestorage.com" \
  --content-type application/json \
  --cache-control "public, max-age=300"

echo "✓ Done."
