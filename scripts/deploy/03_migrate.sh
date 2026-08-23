#!/usr/bin/env bash
# RestaurantOS deploy step 3/4 -- bring up Postgres, run migrations zero
# to head, verify.
#
# The api image's own CMD already runs `alembic upgrade head` before
# uvicorn binds on every container start (see
# infrastructure/docker/api-prod/Dockerfile) -- this script runs it here
# too, explicitly and in isolation (`docker compose run`, not `up`), so a
# migration failure on a fresh database is caught with a clear, single
# purpose-built step instead of buried in the api service's normal
# startup log, before anything else in the deploy sequence proceeds.
#
# Usage (run from the repo root, after scripts/deploy/02_generate_secrets.sh):
#   ./scripts/deploy/03_migrate.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_DIR"
COMPOSE="docker compose -f docker-compose.prod.yml"

if [ ! -f .env ]; then
    echo "ERROR: .env not found in $REPO_DIR -- run scripts/deploy/02_generate_secrets.sh first." >&2
    exit 1
fi

echo "==> Building the api image"
$COMPOSE build api

echo "==> Starting postgres and waiting for it to report healthy"
$COMPOSE up -d postgres
container_id="$($COMPOSE ps -q postgres)"
status=""
for _ in $(seq 1 30); do
    status="$(docker inspect --format '{{.State.Health.Status}}' "$container_id" 2>/dev/null || true)"
    if [ "$status" = "healthy" ]; then
        break
    fi
    sleep 2
done
if [ "$status" != "healthy" ]; then
    echo "ERROR: postgres did not become healthy in time (last status: '$status')." >&2
    echo "Check: $COMPOSE logs postgres" >&2
    exit 1
fi
echo "postgres is healthy."

echo "==> Running migrations (zero to head)"
$COMPOSE run --rm api python -m alembic upgrade head

echo "==> Verifying alembic current == alembic heads"
current="$($COMPOSE run --rm api python -m alembic current 2>/dev/null | head -1)"
heads="$($COMPOSE run --rm api python -m alembic heads 2>/dev/null | head -1)"
echo "current: $current"
echo "heads:   $heads"
current_rev="$(echo "$current" | awk '{print $1}')"
heads_rev="$(echo "$heads" | awk '{print $1}')"
if [ -z "$current_rev" ] || [ "$current_rev" != "$heads_rev" ]; then
    echo "ERROR: database is not at the migration head. current='$current_rev' heads='$heads_rev'" >&2
    exit 1
fi

echo "==> Migrations complete, database at head ($current_rev)."
echo "Next: scripts/deploy/04_bootstrap_platform_admin.sh"
