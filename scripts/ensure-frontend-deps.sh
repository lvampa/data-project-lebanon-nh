#!/usr/bin/env bash
# A new worktree has no node_modules, so `bun x` and tsc would fall back to old global
# tools. Install this tree's own deps from the lockfile first. Does nothing otherwise.
set -euo pipefail

frontend="$(git rev-parse --show-toplevel)/frontend"

if [ ! -d "$frontend/node_modules" ]; then
  # A failed install leaves a partial node_modules, which the next run would trust.
  (cd "$frontend" && bun install --frozen-lockfile) || {
    rm -rf "$frontend/node_modules"
    exit 1
  }
fi
