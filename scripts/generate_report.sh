#!/usr/bin/env bash
# Export Postgres data to data/export. The output is gitignored; local dev serves it with
# `bun run dev` in frontend/web, and a later publish step uploads it.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

urlencode() {
  local LC_ALL=C s="$1" out="" c i
  for ((i = 0; i < ${#s}; i++)); do
    c="${s:i:1}"
    case "$c" in
      [a-zA-Z0-9.~_-]) out+="$c" ;;
      *) printf -v c '%%%02X' "'$c"; out+="$c" ;;
    esac
  done
  printf '%s' "$out"
}

cd "$REPO_ROOT"

# Load .env here so a DATABASE_URL in it wins over the one derived below.
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

if [ -z "${DATABASE_URL:-}" ]; then
  user="$(urlencode "${POSTGRES_USER:-app}")"
  password="$(urlencode "${POSTGRES_PASSWORD:-app}")"
  export DATABASE_URL="postgresql://$user:$password@${POSTGRES_HOST:-localhost}:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-app}"
fi

echo "→ Generating report..."
# The Airflow image has no Rust toolchain, so it sets REPORT_GEN_BIN to a built binary.
if [ -n "${REPORT_GEN_BIN:-}" ]; then
  report_gen=("$REPORT_GEN_BIN")
else
  report_gen=(cargo run -p report-gen --release --)
fi
# The first day of police data the public site covers.
"${report_gen[@]}" \
  --since 2026-01-01 \
  --output-dir "$REPO_ROOT/data/export"
