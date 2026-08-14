#!/usr/bin/env bash
# Restore a RestaurantOS Postgres backup taken by backup_postgres.sh.
#
# Verified manually during Phase 1 against a real migrated schema:
# pg_dump -> DROP DATABASE -> CREATE DATABASE -> pg_restore -> confirmed
# table count (56) and alembic_version (0010) matched the source exactly.
# See docs/RestaurantOS_Production_Deployment_Guide.md "Restore" section.
#
# Usage:
#   DATABASE_USER=... DATABASE_PASSWORD=... DATABASE_NAME=... \
#     ./restore_postgres.sh /var/backups/restaurantos/restaurantos_20260101T030000Z.dump
#
# DESTRUCTIVE: this drops and recreates DATABASE_NAME before restoring.
# Confirms interactively unless CONFIRM=yes is set (for scripted DR
# drills only -- never set it out of habit).

set -euo pipefail

: "${DATABASE_USER:?DATABASE_USER must be set}"
: "${DATABASE_PASSWORD:?DATABASE_PASSWORD must be set}"
: "${DATABASE_NAME:?DATABASE_NAME must be set}"
dump_file="${1:?Usage: restore_postgres.sh <path-to-dump-file>}"

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

compose_file="/opt/restaurantos/docker-compose.prod.yml"

docker compose -f "$compose_file" exec -T -e PGPASSWORD="$DATABASE_PASSWORD" postgres \
    psql -U "$DATABASE_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS ${DATABASE_NAME};" \
    -c "CREATE DATABASE ${DATABASE_NAME};"

docker compose -f "$compose_file" exec -T -e PGPASSWORD="$DATABASE_PASSWORD" postgres \
    pg_restore -U "$DATABASE_USER" -d "$DATABASE_NAME" < "$dump_file"

echo "Restore complete. Verify with:"
echo "  docker compose -f $compose_file exec postgres psql -U $DATABASE_USER -d $DATABASE_NAME -c \"SELECT version_num FROM alembic_version;\""
