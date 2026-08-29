#!/usr/bin/env bash
# Nightly Postgres backup for the RestaurantOS production deployment.
#
# Runs `pg_dump` *inside* the postgres container (`docker compose exec`)
# -- Postgres publishes no host port at all (docker-compose.prod.yml), so
# this is the only way to reach it, and it also avoids needing a
# matching pg_dump client version installed on the host.
#
# Usage: install as a nightly cron job on the VPS (see
# docs/DEPLOYMENT.md's Backup section for the exact crontab line). No
# need to source .env into the caller's shell first -- this script
# sources REPO_DIR/.env itself, below, since every credential it needs
# lives there, never hardcoded here or in the crontab itself.
#
# Required environment (all read from .env, not the caller's shell):
# DATABASE_USER, DATABASE_PASSWORD, DATABASE_NAME, BACKUP_DIR,
# S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
# AWS_DEFAULT_REGION.
# Optional: RETENTION_DAYS (default 7 -- local copies only; the S3 side
# is pruned by the bucket's own lifecycle rule, not by this script --
# see docs/DEPLOYMENT.md).
#
# Off-host copy (S3): the local copy alone doesn't survive this host's
# own failure (disk death, provider incident), so every successful dump
# is also uploaded to S3 immediately, and a failed upload fails this
# whole script loudly (non-zero exit) rather than silently leaving only
# a local copy -- a silent upload failure is worse than no backup, since
# it looks like off-host backup is working when it isn't. The IAM user
# behind AWS_ACCESS_KEY_ID is deliberately write-only (s3:PutObject on
# this one bucket only, no ListBucket/GetObject/DeleteObject, no other
# buckets) -- see docs/DEPLOYMENT.md's Backup section for the exact IAM
# policy. That means this script itself can never read or delete a
# backup it (or a prior run) uploaded, by design: if this box is ever
# compromised, the attacker inherits this same credential and still
# can't read or destroy what's already in S3.
#
# Restore procedure: scripts/deploy/restore.sh <dump-file> -- see that
# script for the automated restore-verification step. Restoring from an
# S3 copy needs a *different*, read-capable credential (your own AWS
# console login or CLI profile) to download it first -- this script's
# own write-only credential structurally cannot do that, on purpose.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$REPO_DIR/docker-compose.prod.yml"

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
: "${DATABASE_NAME:?DATABASE_NAME must be set}"
: "${BACKUP_DIR:?BACKUP_DIR must be set (e.g. /var/backups/restaurantos)}"
: "${S3_BUCKET:?S3_BUCKET must be set}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID must be set}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY must be set}"
: "${AWS_DEFAULT_REGION:?AWS_DEFAULT_REGION must be set (e.g. ap-south-1)}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
filename="restaurantos_${timestamp}.dump"
outfile="$BACKUP_DIR/$filename"

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

if ! aws s3 cp "$outfile" "s3://${S3_BUCKET}/${filename}"; then
    echo "ERROR: upload to s3://${S3_BUCKET}/${filename} failed -- the local dump" >&2
    echo "above is real, but this backup has NO off-host copy. Investigate before" >&2
    echo "assuming tonight's backup is safe." >&2
    exit 1
fi

echo "Uploaded: s3://${S3_BUCKET}/${filename}"

# Local retention only -- the S3-side 30-day retention is a bucket
# lifecycle rule (see docs/DEPLOYMENT.md), not script logic, so it keeps
# working even if this box is down or this script is never run again.
find "$BACKUP_DIR" -name 'restaurantos_*.dump' -mtime "+${RETENTION_DAYS}" -delete
