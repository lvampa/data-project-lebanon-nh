#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

# Load .env so dbt reads the same POSTGRES_* as the export.
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

# The public models are views, so the export reads live rows. Rows written since the
# last DAG run, such as a hand-run normalize, have not met the data checks yet. A
# failing check stops the deploy here, before anything is exported.
echo "→ Building the public models and running their data checks..."
uv run python transform/write_disposition_seed.py
uv run dbt build --project-dir transform --profiles-dir transform

bash "$SCRIPT_DIR/generate_report.sh"

echo "→ Checking the export..."
cargo run -p report-gen --release -- check --dir "$REPO_ROOT/frontend/web/public/data"

echo "→ Building web..."
cd "$REPO_ROOT/frontend/web"
bun run build

echo "→ Deploying to Cloudflare Pages..."
cd "$REPO_ROOT"
wrangler pages deploy frontend/web/out --project-name=lebanon-pd-log --branch=main

echo "✓ Done."
