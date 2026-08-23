#!/usr/bin/env bash
# RestaurantOS deploy step 4/4 -- bring the full stack up, bootstrap the
# first platform-admin account.
#
# Runs services/api/scripts/bootstrap_platform_admin.py *inside* the api
# container (`docker compose exec`) -- with Postgres publishing no host
# port at all, that is the only place a script can reach `postgres:5432`.
# The script itself is idempotent (refuses if a platform admin already
# exists anywhere in the database) and dry-runs by default; this wrapper
# always previews first and asks for a real confirmation before --apply.
#
# Usage (run from the repo root, after scripts/deploy/03_migrate.sh):
#   ./scripts/deploy/04_bootstrap_platform_admin.sh you@prashanthai.com

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_DIR"
COMPOSE="docker compose -f docker-compose.prod.yml"

email="${1:?Usage: 04_bootstrap_platform_admin.sh <admin-email>}"

if [ ! -f .env ]; then
    echo "ERROR: .env not found in $REPO_DIR -- run scripts/deploy/02_generate_secrets.sh first." >&2
    exit 1
fi

echo "==> Bringing up postgres, api, admin-web (not caddy yet -- see docs/DEPLOYMENT.md's DNS step)"
$COMPOSE up -d --build postgres api admin-web

echo "==> Waiting for the api container to report healthy"
container_id="$($COMPOSE ps -q api)"
status=""
for _ in $(seq 1 30); do
    status="$(docker inspect --format '{{.State.Health.Status}}' "$container_id" 2>/dev/null || true)"
    if [ "$status" = "healthy" ]; then
        break
    fi
    sleep 2
done
if [ "$status" != "healthy" ]; then
    echo "ERROR: api did not become healthy in time (last status: '$status')." >&2
    echo "Check: $COMPOSE logs api" >&2
    exit 1
fi
echo "api is healthy."

echo "==> Dry run -- previewing what would be created for $email"
$COMPOSE exec api python scripts/bootstrap_platform_admin.py --email "$email"

echo
read -r -p "Proceed with --apply? Type 'yes' to continue: " reply
if [ "$reply" != "yes" ]; then
    echo "Aborted -- nothing was written."
    exit 1
fi

$COMPOSE exec api python scripts/bootstrap_platform_admin.py --email "$email" --apply

echo
echo "==> Platform admin bootstrapped. Copy the email/password/tenantId printed above"
echo "    somewhere safe now -- the password is never shown again."
echo "Next: point DNS at this host, fill in CADDY_ACME_EMAIL in .env if you left the"
echo "placeholder, then: $COMPOSE up -d caddy"
echo "See docs/DEPLOYMENT.md for the remaining steps (DNS, HTTPS verification, smoke test)."
