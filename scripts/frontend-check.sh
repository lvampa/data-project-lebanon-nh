#!/usr/bin/env bash
# The pre-push frontend check: typecheck and test the whole frontend.
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
bash "$repo_root/scripts/ensure-frontend-deps.sh"

cd "$repo_root/frontend"
bun run --filter '*' typecheck
bun run test
