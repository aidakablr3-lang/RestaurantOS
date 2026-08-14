#!/usr/bin/env bash
# Nightly Postgres backup for a RestaurantOS pilot deployment.
#
# Design tested manually against a real migrated database during Phase 1
# (dump -> drop -> restore -> verify table count and alembic_version) --
# see docs/RestaurantOS_Production_Deployment_Guide.md "Backup" section
# for that verification record. This script wraps the same two commands
# (pg_dump/pg_restore) for unattended cron use, nothing more.
#
# Usage: run on the VPS, as a daily cron job, against the Postgres
# container started by docker-compose.prod.yml:
#   0 3 * * * /opt/restaurantos/infrastructure/scripts/backup_postgres.sh
#
# Required environment (set in the crontab entry or an env file it
# sources -- never hardcode credentials into this script):
#   DATABASE_USER, DATABASE_PASSWORD, DATABASE_NAME, BACKUP_DIR
# Optional: RETENTION_DAYS (default 14).

set -euo pipefail

: "${DATABASE_USER:?DATABASE_USER must be set}"
: "${DATABASE_PASSWORD:?DATABASE_PASSWORD must be set}"
: "${DATABASE_NAME:?DATABASE_NAME must be set}"
: "${BACKUP_DIR:?BACKUP_DIR must be set (e.g. /var/backups/restaurantos)}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
outfile="$BACKUP_DIR/restaurantos_${timestamp}.dump"

# Runs pg_dump *inside* the postgres container -- avoids needing a
# matching pg_dump client version installed on the host, and the
# container already has the exact server-version-matched tooling.
docker compose -f /opt/restaurantos/docker-compose.prod.yml exec -T \
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

# Retention: delete backups older than RETENTION_DAYS. Off-host copy
# (rclone/rsync/cloud CLI to storage outside this VPS) is deliberately
# NOT done here -- a disk-only backup on the same machine you're
# protecting against doesn't survive that machine's own failure. Wire
# up whichever off-host destination the pilot actually uses (S3-
# compatible bucket, Backblaze B2, a second VPS) as an additional step
# appended here before go-live -- see the deployment guide's "Backup"
# section for the specific recommendation.
find "$BACKUP_DIR" -name 'restaurantos_*.dump' -mtime "+${RETENTION_DAYS}" -delete
