#!/usr/bin/env bash
# Generates a local-only RS256 keypair for `docker compose up`.
#
# Run this once before your first `docker compose up` (see
# docs/DEVELOPMENT.md). The keypair is written next to this script and
# is gitignored -- it never gets committed. Delete private.pem/public.pem
# and re-run this script to rotate it; nothing depends on the key's
# value staying fixed across machines or runs.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRIVATE_KEY="$DIR/private.pem"
PUBLIC_KEY="$DIR/public.pem"

if [[ -f "$PRIVATE_KEY" || -f "$PUBLIC_KEY" ]]; then
  echo "Dev JWT keypair already exists at $DIR"
  echo "Delete private.pem and public.pem first if you want to regenerate it."
  exit 0
fi

openssl genrsa -out "$PRIVATE_KEY" 2048
openssl rsa -in "$PRIVATE_KEY" -pubout -out "$PUBLIC_KEY"
chmod 600 "$PRIVATE_KEY" 2>/dev/null || true

echo "Generated a local-only dev JWT keypair at $DIR"
echo "Never commit private.pem or public.pem -- .gitignore already excludes them."
