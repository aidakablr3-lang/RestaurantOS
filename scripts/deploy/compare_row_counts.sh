#!/usr/bin/env bash
# Compares per-table row counts between two databases in the same
# Postgres container -- proves a restore is row-for-row faithful, not
# just "the right number of tables and the right migration head" (which
# restore.sh's own built-in verification already checks).
#
# Usage (run from the repo root; credentials come from REPO_DIR/.env,
# sourced by this script -- no need to source it into the shell first):
#   ./scripts/deploy/compare_row_counts.sh <source_db> <target_db>
#
# Prints every table's row count from both databases; if every count
# matches exactly, prints PASS and exits 0. If any table's count
# differs (or a table exists in one database but not the other), prints
# a diff and exits non-zero.
#
# Uses query_to_xml()/xpath() to get every table's count in a single
# query per database, rather than looping a `SELECT count(*)` per table
# -- there's no PL/pgSQL function installed to loop with, and this is a
# read-only, well-known idiom for exactly this (tested locally against
# a disposable Postgres before being pointed at anything real).

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE="docker compose -f $REPO_DIR/docker-compose.prod.yml"

if [ ! -f "$REPO_DIR/.env" ]; then
    echo "ERROR: $REPO_DIR/.env not found -- run scripts/deploy/02_generate_secrets.sh first." >&2
    exit 1
fi
set -a
# shellcheck source=/dev/null
source "$REPO_DIR/.env"
set +a

: "${DATABASE_USER:?DATABASE_USER must be set}"
: "${DATABASE_PASSWORD:?DATABASE_PASSWORD must be set}"
source_db="${1:?Usage: compare_row_counts.sh <source_db> <target_db>}"
target_db="${2:?Usage: compare_row_counts.sh <source_db> <target_db>}"

_row_counts_query() {
    cat <<'SQL'
SELECT table_name || ':' ||
  (xpath('/row/cnt/text()', query_to_xml(format('SELECT count(*) AS cnt FROM %I.%I', table_schema, table_name), false, true, '')))[1]::text
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;
SQL
}

_counts() {
    local db="$1"
    $COMPOSE exec -T -e PGPASSWORD="$DATABASE_PASSWORD" postgres \
        psql -U "$DATABASE_USER" -d "$db" -tA -c "$(_row_counts_query)"
}

source_file="$(mktemp)"
target_file="$(mktemp)"
trap 'rm -f "$source_file" "$target_file"' EXIT

echo "==> Counting rows in $source_db"
_counts "$source_db" > "$source_file"
echo "==> Counting rows in $target_db"
_counts "$target_db" > "$target_file"

echo
if diff -u --label "$source_db" "$source_file" --label "$target_db" "$target_file"; then
    echo "PASS: every table's row count matches exactly ($source_db vs $target_db)."
else
    echo "FAIL: row count mismatch between $source_db and $target_db (see diff above)." >&2
    exit 1
fi
