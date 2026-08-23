#!/usr/bin/env bash
# Nightly Postgres backup for the RestaurantOS production deployment.
#
# Runs `pg_dump` *inside* the postgres container (`docker compose exec`)
# -- Postgres publishes no host port at all (docker-compose.prod.yml), so
# this is the only way to reach it, and it also avoids needing a
# matching pg_dump client version installed on the host.
#
# Usage: install as a nightly cron job on the VPS:
#   0 3 * * * DATABASE_USER=restaurantos DATABASE_PASSWORD=... DATABASE_NAME=restaurantos \
#       BACKUP_DIR=/var/backups/restaurantos /opt/restaurantos/scripts/deploy/backup.sh
# (source the real DATABASE_PASSWORD from /opt/restaurantos/.env in the
# crontab entry or a small env file it sources -- never hardcode it here.)
#
# Required environment: DATABASE_USER, DATABASE_PASSWORD, DATABASE_NAME, BACKUP_DIR.
# Optional: RETENTION_DAYS (default 14).
#
# Restore procedure: scripts/deploy/restore.sh <dump-file> -- see that
# script for the automated restore-verification step.
#
# Off-host copy is deliberately NOT done here -- a same-host-only backup
# doesn't survive that host's own failure (disk death, provider
# incident). Before go-live, append an off-host step (rclone to an
# S3-compatible bucket, Backblaze B2, or scp to a second machine) --
# left as a placeholder rather than guessing at a provider you haven't
# chosen. See docs/DEPLOYMENT.md's Backup section.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$REPO_DIR/docker-compose.prod.yml"

: "${DATABASE_USER:?DATABASE_USER must be set}"
: "${DATABASE_PASSWORD:?DATABASE_PASSWORD must be set}"
: "${DATABASE_NAME:?DATABASE_NAME must be set}"
: "${BACKUP_DIR:?BACKUP_DIR must be set (e.g. /var/backups/restaurantos)}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
outfile="$BACKUP_DIR/restaurantos_${timestamp}.dump"

docker compose -f "$COMPOSE_FILE" exec -T \
    -e PGPASSWORD="$DATABASE_PASSWORD" \
    postgres \
    pg_dump -U "$DATABASE_USER" -d "$DATABASE_NAME" -F c \
    > "$outfile"

# A zero-byte or truncated dump is worse than no backup (false
# confidence) -- fail loudly instead of silently leaving a bad file.
if [ ! -s "$outfile" ]; then
    echo "ERROR: backup file is empty: $outfile" >&2
    rm -f "$outfile"
    exit 1
fi

echo "Backup written: $outfile ($(du -h "$outfile" | cut -f1))"

find "$BACKUP_DIR" -name 'restaurantos_*.dump' -mtime "+${RETENTION_DAYS}" -delete
