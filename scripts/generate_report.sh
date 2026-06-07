#!/usr/bin/env bash
# Generate public/data JSON locally and commit it so CI can deploy without
# needing database access.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "→ Generating report..."
cd "$REPO_ROOT/scrapers"
uv run python scripts/generate_report.py

echo "→ Committing public/data/..."
cd "$REPO_ROOT"
git add frontend/web/public/data/
git diff --cached --quiet && echo "  (no changes)" && exit 0
git commit -m "chore: update public data $(date -u +%Y-%m-%d)"

echo "✓ Done. Push to trigger CI deploy."
