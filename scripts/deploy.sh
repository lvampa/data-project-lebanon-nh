#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "→ Building web..."
cd "$REPO_ROOT/frontend/web"
bun run build

echo "→ Deploying to Cloudflare Pages..."
cd "$REPO_ROOT"
wrangler pages deploy frontend/web/out --project-name=lebanon-pd-log --branch=main

echo "✓ Done."
