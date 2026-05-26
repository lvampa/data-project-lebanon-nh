#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "→ Generating report..."
cd "$SCRIPT_DIR/scrapers"
uv run python scripts/generate_report.py

echo "→ Deploying to Cloudflare Pages..."
cd "$SCRIPT_DIR"
wrangler pages deploy public --project-name=lebanon-pd-log --branch=main

echo "✓ Done."
