#!/usr/bin/env bash
# Export the report data, check it, and sync it to the R2 bucket the site reads from.
# From the repo root: bash scripts/deploy-data.sh [--dry-run]
# --dry-run exports and checks, then stops before the upload.
#
# The upload needs R2_BUCKET, an endpoint, and credentials for one R2 API token with Object
# Read & Write on that one bucket. The endpoint is R2_ENDPOINT, or built from
# CLOUDFLARE_ACCOUNT_ID. The credentials are either AWS_PROFILE, an aws CLI profile made with
# `aws configure --profile <name>` (a hand run), or AWS_ACCESS_KEY_ID and
# AWS_SECRET_ACCESS_KEY (Airflow's publish_data task, which reads them from a Connection).
# Nothing is printed from the environment, and the script never turns on tracing.
set -euo pipefail

die() {
  echo "deploy-data: $1" >&2
  exit 1
}

[ -f scripts/deploy-data.sh ] && [ -f scripts/generate_report.sh ] || die "Run scripts/deploy-data.sh from the repo root."

case "$*" in
  "") dry_run=false ;;
  --dry-run) dry_run=true ;;
  *) die "unknown argument '$*'; the only option is --dry-run" ;;
esac

# A value counts as set only when it is not empty and not the text "None", which is what a
# template renders for a missing Connection field.
is_set() {
  [ -n "${1:-}" ] && [ "${1:-}" != "None" ]
}

# Fail before the slow export, not after it.
if ! $dry_run; then
  is_set "${R2_BUCKET:-}" || die "R2_BUCKET is not set"
  if is_set "${R2_ENDPOINT:-}"; then
    endpoint="$R2_ENDPOINT"
  elif is_set "${CLOUDFLARE_ACCOUNT_ID:-}"; then
    endpoint="https://$CLOUDFLARE_ACCOUNT_ID.r2.cloudflarestorage.com"
  else
    die "set R2_ENDPOINT or CLOUDFLARE_ACCOUNT_ID"
  fi
  has_key_pair=false
  if is_set "${AWS_ACCESS_KEY_ID:-}" && is_set "${AWS_SECRET_ACCESS_KEY:-}"; then
    has_key_pair=true
  fi
  if is_set "${AWS_PROFILE:-}" && $has_key_pair; then
    die "set AWS_PROFILE or the key pair, not both"
  fi
  if ! is_set "${AWS_PROFILE:-}" && ! $has_key_pair; then
    die "set AWS_PROFILE, or both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
  fi
fi

# The R2 credentials belong to the upload alone. Everything before it runs without them.
without_r2_credentials() {
  env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_PROFILE "$@"
}

# Hold flagged locations that are not clearly safe, so the export leaves them out. It only
# adds holds, and prints counts.
echo "→ Holding unsafe person locations..."
without_r2_credentials uv run --frozen privacy-holds mark

echo "→ Exporting the report data..."
without_r2_credentials bash scripts/generate_report.sh

# Nothing is uploaded unless every check passes. The checks print counts, never the text.
echo "→ Checking the export..."
without_r2_credentials uv run --frozen check-export data/export

if $dry_run; then
  echo "✓ Dry run, not uploading."
  exit 0
fi

# R2 rejects the checksum headers that newer aws versions add by default.
export AWS_REQUEST_CHECKSUM_CALCULATION=when_required
export AWS_RESPONSE_CHECKSUM_VALIDATION=when_required

# --delete drops a place card that is gone. The bucket holds only this export, so say which
# bucket and host this is before anything is removed.
endpoint_host="${endpoint#https://}"
echo "→ Syncing to bucket $R2_BUCKET at ${endpoint_host%%/*}..."
aws s3 sync data/export "s3://$R2_BUCKET/" \
  --delete \
  --region auto \
  --endpoint-url "$endpoint" \
  --content-type application/json \
  --cache-control "public, max-age=300"

echo "✓ Done."
