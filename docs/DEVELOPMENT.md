# Local Development Setup

Two ways to get a working `services/api` + PostgreSQL stack: Docker
Compose (recommended, one command) or a manual native setup (documented
because Docker isn't available in every environment -- this is exactly
how the Tenant Platform sprint itself was developed and tested).
`apps/admin-web` runs the same way either way: `npm run dev`, outside
Docker, for fast Fast Refresh.

## Prerequisites

- **Docker Desktop** (or Docker Engine + Compose plugin) -- for the
  Docker Compose path.
- **Python 3.13+** and **Node.js 20+** -- for the manual path, and for
  `apps/admin-web` regardless of which backend path you choose.
- **PostgreSQL 17 client tools** (`psql`, `pg_ctl`, `initdb`) on your
  `PATH` -- only needed for the manual path.

## Option A: Docker Compose (recommended)

```bash
./infrastructure/docker/dev-jwt/generate-dev-keys.sh   # one-time; see below
docker compose up
```

This builds and starts `postgres` + `api` (see `docker-compose.yml`),
runs migrations automatically on container start, and serves the API
on `http://localhost:8000` with hot reload (source-mounted, `uvicorn
--reload`).

**JWT keys are generated locally, not committed.** The first command
above creates a local-only RS256 keypair at
`infrastructure/docker/dev-jwt/{private,public}.pem` (gitignored) that
`docker-compose.yml` mounts into the `api` container. It's idempotent
-- safe to run every time, it only generates a key if one doesn't
already exist. Use `generate-dev-keys.py` instead if you don't have
`openssl` on your `PATH` but do have Python (same output). See
`infrastructure/docker/dev-jwt/README.md`.

To also run the frontend:

```bash
cd apps/admin-web
cp .env.local.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`. First run needs a platform-admin user to
log in with -- see [Seeding a user](#seeding-a-platform-admin-user)
below.

**Overriding defaults:** copy `services/api/.env.example` to
`services/api/.env` and edit `DATABASE_USER`/`PASSWORD`/`NAME`/
`HOST_PORT` or `CORS_ALLOWED_ORIGINS` if you need something other than
the defaults (e.g. port `5433` already in use). Docker Compose reads
`services/api/.env`... actually reads a `.env` file in the same
directory as `docker-compose.yml` (repo root) by default -- if you
override values, put them in a root-level `.env` (gitignored), not
`services/api/.env`.

**Note:** this repo's Docker setup was authored and syntax-validated
(`docker compose config`-equivalent YAML parsing) but not run against
a live Docker daemon in the environment that built it -- Docker wasn't
installed there. One real build-breaking bug was already found and
fixed this way (`infrastructure/docker/api/Dockerfile` installed the
package before its source existed in the image, permanently breaking
the import -- confirmed and fixed by reproducing the exact pip/
setuptools sequence outside Docker, see `docs/releases/v0.1.0-rc1.md`),
but a full `docker compose up --build` has still never actually run.
If it doesn't work as described, that's the first thing to check;
please fix forward and update this
doc rather than assuming it's untestable.

## Option B: Manual native setup

The exact sequence Sprint 4.1's own Step 3/4 verification used against
a real backend, no Docker required.

```bash
# 1. PostgreSQL 17
winget install --id PostgreSQL.PostgreSQL.17   # Windows; use your OS's
                                                 # package manager otherwise

# 2. A standalone instance you own, on a port that won't collide with
#    any other local Postgres (adjust the port/path as needed)
initdb -D <some-data-dir> -U restaurantos --auth=trust -E UTF8
pg_ctl start -D <some-data-dir> -o "-p 5433 -c listen_addresses=localhost" -l <some-data-dir>/logfile
createdb -h localhost -p 5433 -U restaurantos restaurantos

# 3. RS256 dev keypair
openssl genrsa -out jwt_private.pem 2048
openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem

# 4. Python env + migrations
cd services/api
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows
# source .venv/bin/activate && pip install -e ".[dev]"  # macOS/Linux
export JWT_PRIVATE_KEY="$(cat ../../jwt_private.pem)" JWT_PUBLIC_KEY="$(cat ../../jwt_public.pem)"
export DATABASE_URL="postgresql+asyncpg://restaurantos@localhost:5433/restaurantos"
python -m alembic upgrade head

# 5. Run the API
export APP_ENV=development
export CORS_ALLOWED_ORIGINS="http://localhost:3000"
python -m uvicorn restaurant_os_api.main:app --host 127.0.0.1 --port 8000 --reload
```

Then the frontend, same as Option A.

## Seeding a platform-admin user

There is no user-creation UI or endpoint yet (Sprint 4.1 Decision C --
an interim `is_platform_admin` boolean, no RBAC/admin-invite flow). Use
the committed seed script, idempotent, works against either setup:

```bash
cd services/api
# Docker Compose: run inside the api container instead --
#   docker compose exec api python scripts/seed_e2e_fixtures.py
DATABASE_URL=<your database URL> python scripts/seed_e2e_fixtures.py
```

Prints the tenant ID, email, and password to log in with at
`http://localhost:3000/login`.

## Running tests

```bash
cd services/api

# Unit tests -- no database needed
JWT_PRIVATE_KEY=dummy JWT_PUBLIC_KEY=dummy python -m pytest tests/unit -q

# Full suite including integration tests -- needs a real Postgres
# (a *disposable* database: truncated between tests, migrated up/down
# around the whole run)
JWT_PRIVATE_KEY=dummy JWT_PUBLIC_KEY=dummy \
  TEST_DATABASE_URL="postgresql+asyncpg://restaurantos@localhost:5433/restaurantos_test" \
  python -m pytest tests/ -q
```

```bash
cd apps/admin-web
npx tsc --noEmit && npx eslint .
npm run build

# End-to-end (needs a running backend + the seed script run against it
# -- see apps/admin-web/e2e/README.md)
npx playwright install chromium   # first time only
export E2E_ADMIN_TENANT_ID=<tenantId the seed script printed>
npm run e2e
```

## Generating an OpenAPI export

```bash
cd services/api
python scripts/export_openapi.py
```

Writes `docs/api/openapi.json` from the running app's route
definitions -- no server needs to be running. Regenerate and commit
whenever a route's request/response shape changes. See
`docs/api/README.md`.

## Troubleshooting

- **Port already in use:** something else (another Postgres, another
  dev server) is likely already on `5433`/`8000`/`3000`. Change the
  relevant port (see `.env.example`s) rather than killing the other
  process blind.
- **`asyncio.run() cannot be called from a running event loop`** when
  running integration tests: this was a real bug, fixed in
  `tests/integration/conftest.py` (see `docs/AI_HANDOFF.md`'s Step 4
  section). If you see it again, something regressed that fix.
- **A platform-admin suspending their own tenant gets logged out
  immediately:** correct behavior, not a bug -- suspending a tenant
  revokes every session belonging to it, including the admin's own if
  they happen to live in that tenant. Seed a second tenant (or use
  `scripts/seed_e2e_fixtures.py`'s dedicated one) for the admin
  identity you test with.
