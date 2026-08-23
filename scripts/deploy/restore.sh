#!/usr/bin/env bash
# Restore a RestaurantOS Postgres backup taken by scripts/deploy/backup.sh,
# with an automated restore-verification step (not just a suggestion to
# check manually).
#
# Usage:
#   DATABASE_USER=... DATABASE_PASSWORD=... DATABASE_NAME=... \
#     ./scripts/deploy/restore.sh /var/backups/restaurantos/restaurantos_20260101T030000Z.dump
#
# DESTRUCTIVE: this drops and recreates DATABASE_NAME before restoring.
# Confirms interactively unless CONFIRM=yes is set (for scripted DR
# drills only -- never set it out of habit).
#
# Verification, run automatically after every restore:
#   1. `alembic_version` in the restored database matches `alembic heads`
#      for the code currently checked out (via the api image, so it's
#      exactly the migration chain that's actually deployed, not a
#      number copy-pasted into this script that would go stale).
#   2. At least one table exists in the `public` schema (catches a
#      restore that "succeeded" into an empty database).
# Exits non-zero if either check fails -- a restore that silently
# produced a wrong or empty database is worse than one that fails loudly.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$REPO_DIR/docker-compose.prod.yml"
COMPOSE="docker compose -f $COMPOSE_FILE"

: "${DATABASE_USER:?DATABASE_USER must be set}"
: "${DATABASE_PASSWORD:?DATABASE_PASSWORD must be set}"
: "${DATABASE_NAME:?DATABASE_NAME must be set}"
dump_file="${1:?Usage: restore.sh <path-to-dump-file>}"

if [ ! -f "$dump_file" ]; then
    echo "ERROR: dump file not found: $dump_file" >&2
    exit 1
fi

if [ "${CONFIRM:-}" != "yes" ]; then
    read -r -p "This will DROP and recreate '$DATABASE_NAME' and restore $dump_file. Type 'yes' to continue: " reply
    if [ "$reply" != "yes" ]; then
        echo "Aborted."
        exit 1
    fi
fi

echo "==> Dropping and recreating $DATABASE_NAME"
$COMPOSE exec -T -e PGPASSWORD="$DATABASE_PASSWORD" postgres \
    psql -U "$DATABASE_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS ${DATABASE_NAME};" \
    -c "CREATE DATABASE ${DATABASE_NAME};"

echo "==> Restoring $dump_file"
$COMPOSE exec -T -e PGPASSWORD="$DATABASE_PASSWORD" postgres \
    pg_restore -U "$DATABASE_USER" -d "$DATABASE_NAME" < "$dump_file"

echo "==> Verifying restore"

expected_head="$($COMPOSE run --rm api python -m alembic heads 2>/dev/null | head -1 | awk '{print $1}')"
restored_version="$($COMPOSE exec -T -e PGPASSWORD="$DATABASE_PASSWORD" postgres \
    psql -U "$DATABASE_USER" -d "$DATABASE_NAME" -tA \
    -c "SELECT version_num FROM alembic_version;" | tr -d '[:space:]')"
table_count="$($COMPOSE exec -T -e PGPASSWORD="$DATABASE_PASSWORD" postgres \
    psql -U "$DATABASE_USER" -d "$DATABASE_NAME" -tA \
    -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d '[:space:]')"

echo "Expected migration head: $expected_head"
echo "Restored alembic_version: $restored_version"
echo "Restored table count: $table_count"

failed=0
if [ -z "$restored_version" ] || [ "$restored_version" != "$expected_head" ]; then
    echo "FAIL: restored alembic_version does not match the current code's migration head." >&2
    failed=1
fi
if [ -z "$table_count" ] || [ "$table_count" -eq 0 ]; then
    echo "FAIL: restored database has zero tables in the public schema." >&2
    failed=1
fi

if [ "$failed" -ne 0 ]; then
    echo "RESTORE VERIFICATION FAILED -- do not treat this restore as trustworthy." >&2
    exit 1
fi

echo "RESTORE VERIFICATION PASSED."
