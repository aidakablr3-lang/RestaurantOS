#!/usr/bin/env bash
# RestaurantOS deploy orchestrator -- runs 01 through 04 in order.
#
# This is the "single run once the box exists" entry point: server
# hardening, secret generation, migrations, and platform-admin bootstrap,
# back to back, each step's own safety checks (won't overwrite an
# existing .env, won't duplicate a platform admin, requires a typed
# 'yes' before writing) still apply -- this script does not bypass any
# of them, it just chains the four steps so you don't have to run them
# by hand one at a time.
#
# What this does NOT do (still manual, deliberately -- see
# docs/DEPLOYMENT.md): point DNS at this host, start caddy (needs DNS
# live first), run the smoke test. Those come after this script finishes.
#
# Usage (run as root, from the repo root, e.g. /opt/restaurantos):
#   ./scripts/deploy/deploy.sh --acme-email you@prashanthai.com --admin-email you@prashanthai.com

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_DIR"

acme_email=""
admin_email=""

while [ $# -gt 0 ]; do
    case "$1" in
        --acme-email)
            acme_email="$2"
            shift 2
            ;;
        --admin-email)
            admin_email="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

if [ -z "$acme_email" ] || [ -z "$admin_email" ]; then
    echo "Usage: deploy.sh --acme-email <email> --admin-email <email>" >&2
    exit 1
fi

echo "########## Step 1/4: server setup ##########"
bash "$REPO_DIR/scripts/deploy/01_server_setup.sh"

echo "########## Step 2/4: generate secrets ##########"
bash "$REPO_DIR/scripts/deploy/02_generate_secrets.sh" --acme-email "$acme_email"

echo "########## Step 3/4: migrate ##########"
bash "$REPO_DIR/scripts/deploy/03_migrate.sh"

echo "########## Step 4/4: bootstrap platform admin ##########"
bash "$REPO_DIR/scripts/deploy/04_bootstrap_platform_admin.sh" "$admin_email"

echo
echo "########## Done ##########"
echo "Remaining manual steps (docs/DEPLOYMENT.md): point DNS at this host's IP,"
echo "then: docker compose -f docker-compose.prod.yml up -d caddy"
echo "then run the smoke test."
