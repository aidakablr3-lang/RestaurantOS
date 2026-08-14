# RestaurantOS — Production Deployment Guide

**Status as of this writing:** `develop` @ commit `a06902e` (post PR #1 merge — Restaurant Platform, Day-to-Day Operations, RBAC, guest QR ordering, all of Sprints 5-7). This guide is written for the **first hotel pilot deployment** — one hotel, one restaurant, one branch. Multi-hotel/multi-region concerns are explicitly out of scope; revisit when a second pilot is contracted.

This document is the output of Phase 1 (Release/Deployment readiness). It describes a **recommended, validated-in-a-disposable-environment** production architecture. No real server, domain, or production data has been touched — see §19.

---

## 1. Architecture

```
Guest's phone / Staff laptop
        |  HTTPS
        v
   Caddy (reverse proxy + automatic TLS, runs on the VPS)
        |                              |
        v                              v
apps/admin-web                   services/api
(Next.js, systemd,               (FastAPI, Docker container,
 127.0.0.1:3000)                  127.0.0.1:8000)
                                        |
                                        v
                                  PostgreSQL 17
                                  (Docker container,
                                   127.0.0.1:5432 only)
```

**Why this shape, not something else** (per Phase 1 Step 2's own instruction to compare options and justify, not default to the popular choice):

- **One VPS, not Kubernetes/managed PaaS.** A single hotel pilot has, at most, a few dozen concurrent staff+guest connections. Kubernetes' orchestration overhead buys nothing at this scale and multiplies the operational surface a two-person team has to babysit during a pilot. A managed PaaS (Render/Railway/Fly.io) would work but means adopting a new platform with zero existing project investment, for no capability this VPS shape doesn't already provide at this scale.
- **Postgres + API in Docker, frontend not.** `docker-compose.yml` (the existing dev file) already containerizes Postgres and the API but *deliberately* does not containerize `apps/admin-web` — its own comment explains why: Next.js's production server is already a single long-running Node process, and adding a second image to build/tag/redeploy buys nothing at one-VPS scale. This guide keeps that precedent rather than introducing new complexity the project's own dev environment already rejected.
- **Caddy, not nginx, for the reverse proxy.** `infrastructure/nginx/` exists in the repo as an empty placeholder, but this guide recommends **Caddy** instead: automatic Let's Encrypt issuance and renewal with zero additional tooling (no certbot, no renewal cron, no separate ACME client to patch). For a from-scratch single-VPS setup with no existing nginx investment, that removes an entire operational surface. Revisit if the pilot grows into a CDN-fronted or multi-node setup where nginx's/a load balancer's ecosystem starts to matter more than initial setup simplicity.
- **Self-hosted Postgres, not a managed database service.** At one-hotel scale, a managed Postgres service (RDS, Cloud SQL, etc.) adds cost and a second vendor relationship for a workload a single container with disciplined backups (§13) handles fine. Revisit if/when multi-hotel scale makes managed HA and point-in-time-recovery worth the added cost and complexity.

---

## 2. Prerequisites

- A VPS or equivalent host: minimum 2 vCPU / 4GB RAM / 40GB SSD for this scale (Postgres + API container + Node process comfortably fit; headroom for the pilot's own guest QR traffic spikes at meal times).
- Docker Engine + Docker Compose v2 installed on the host.
- Node.js 20+ and npm installed on the host (for `apps/admin-web`'s build/run — not containerized, see §1).
- A domain you control, with DNS access (see §4).
- `git` on the host, or a CI/CD pipeline that pushes built artifacts — this guide assumes the simpler `git pull` + rebuild path, matching the project's current stage (no image registry or CD pipeline exists yet — see §16).

## 3. Server Requirements

See §2 — no GPU, no special hardware. A single VPS is sufficient for one pilot hotel. Ensure the host firewall (ufw/nftables) only exposes ports 80/443 publicly; every application port (3000, 8000, 5432) must bind to `127.0.0.1` only, reached solely through Caddy — `docker-compose.prod.yml` and the systemd unit example in this repo already bind this way (see §5).

## 4. Domain Requirements

Two subdomains are enough for the first pilot:

- `admin.<your-domain>` → `apps/admin-web` (staff/manager/waiter/cashier/inventory login, and the guest QR ordering pages, which live in the same Next.js app's `(guest)` route group).
- `api.<your-domain>` → `services/api` (called directly by both the admin app's server-side code and guests' browsers).

Point both A/AAAA records at the VPS's IP before starting Caddy (see `infrastructure/reverse-proxy/Caddyfile.example` — replace `your-hotel-domain.com` with the real domain).

## 5. Environment Variables

| Variable | Component | Required | Secret? | Production source | Example |
|---|---|---|---|---|---|
| `APP_ENV` | API | Yes | No | Set literally to `production` | `production` |
| `DATABASE_URL` | API | Yes | Yes (embeds password) | Constructed by `docker-compose.prod.yml` from `DATABASE_*` below | `postgresql+asyncpg://restaurantos:***@postgres:5432/restaurantos` |
| `DATABASE_USER` | API + Postgres | No (defaults `restaurantos`) | No | Your choice | `restaurantos` |
| `DATABASE_PASSWORD` | API + Postgres | Yes | **Yes** | Generate with `openssl rand -base64 32`; store only in the host's `.env` (root-readable only, `chmod 600`) | — |
| `DATABASE_NAME` | API + Postgres | No (defaults `restaurantos`) | No | Your choice | `restaurantos` |
| `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` | API | Yes | **Yes** (private key) | Generate a real RS256 keypair for this deployment (`openssl genrsa`/`openssl rsa -pubout`, same commands `docs/DEVELOPMENT.md` uses for dev) — **never reuse the dev keypair or any keypair from this repo's history** | full PEM content, not a path |
| `CORS_ALLOWED_ORIGINS` | API | Yes | No | The real `admin.<your-domain>` origin, exactly | `https://admin.your-hotel-domain.com` |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend | Yes | No | The real `api.<your-domain>` origin — **baked in at `npm run build` time**, not read at runtime (Next.js convention); changing it requires a rebuild, not just a restart | `https://api.your-hotel-domain.com` |
| `JWT_ACCESS_TTL_SECONDS` / `JWT_REFRESH_TTL_SECONDS` / `JWT_ISSUER` | API | No | No | Defaults (900s / 30d / `restaurantos`) are sane for a pilot | — |
| `DATABASE_POOL_SIZE` | API | No (defaults 10) | No | Raise only if connection-pool exhaustion is observed | — |

Notes carried over from live findings, not guesses:
- `DatabaseSettings`/`JWTSettings` are separate `pydantic-settings` models that do **not** inherit the parent `Settings`' `env_file=".env"` config — a documented, pre-existing gap (P1-3 in the Hotel Pilot Readiness Review). In practice this means: **these values must be real process/shell environment variables**, not just present in a `.env` file that nothing reads. `docker-compose.prod.yml` handles this correctly (Compose's own `.env`-file support sets real container environment variables); if running the API outside Docker, export them in the shell/systemd unit explicitly.
- No secrets manager exists yet (confirmed: `infrastructure/docker/dev-jwt/` is explicitly dev-only, and this is `RELEASE_CHECKLIST.md`'s own disclosed gap). For one pilot hotel, a root-only `.env` file on the VPS is an acceptable starting point; revisit before a second hotel.
- I am not generating real production JWT keys or passwords for you — per Phase 1's own instruction, those must be generated and supplied by you when the real server exists.

## 6. Database Setup

```bash
# One-time, on the VPS, after docker-compose.prod.yml and .env are in place:
docker compose -f docker-compose.prod.yml up -d postgres
# Migrations run automatically on API container start (see infrastructure/docker/api-prod/Dockerfile's CMD) --
# no separate manual step needed for a fresh deploy.
docker compose -f docker-compose.prod.yml up -d api
```

**Verified during Phase 1** against a disposable database (not this guide's claim alone):
- Clean `alembic upgrade head` from an empty database: all 10 migrations (`0001`→`0010`) applied without error.
- `alembic current` == `alembic heads` (`0010`) after upgrade.
- Full `alembic downgrade base` then `alembic upgrade head` cycle: clean both directions, no errors.
- Resulting schema: 56 tables, 48 with row-level security enabled.
- Migration chain is linear (`0001`'s `down_revision` is `None`; every subsequent migration's `down_revision` points to exactly one predecessor; every one of the 10 files defines both `upgrade()` and `downgrade()`).

## 7. Backend Deployment

```bash
git clone <repo-url> /opt/restaurantos && cd /opt/restaurantos
git checkout develop   # or the specific release commit/tag once one exists -- see §16
cp services/api/.env.example .env   # then fill in real values per §5, chmod 600 .env
docker compose -f docker-compose.prod.yml up -d --build
curl -sf https://api.your-hotel-domain.com/health/live   # expect {"status":"ok"}
```

The production image (`infrastructure/docker/api-prod/Dockerfile`, new in this phase) differs from the existing `infrastructure/docker/api/Dockerfile` (which is explicitly dev-only — bind-mounted source, `--reload`, runs as root): multi-stage build, immutable (no bind mount), runs as a non-root user, no `--reload`, includes a `HEALTHCHECK`.

## 8. Frontend Deployment

```bash
cd /opt/restaurantos/apps/admin-web
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_BASE_URL to the real API origin
npm ci
npm run build
sudo cp /opt/restaurantos/infrastructure/systemd/restaurantos-web.service.example \
    /etc/systemd/system/restaurantos-web.service   # adjust User/WorkingDirectory first
sudo systemctl daemon-reload
sudo systemctl enable --now restaurantos-web
```

**Verified during Phase 1**: `tsc --noEmit`, `eslint`, Vitest (169/169, 47 files), and `next build --turbopack` all clean against this exact `develop` HEAD (the AI_HANDOFF-only commit on top of the merge changed no application code, so the E2E-fix verification from immediately before the merge still applies unchanged).

## 9. HTTPS

Install Caddy on the VPS, then use `infrastructure/reverse-proxy/Caddyfile.example` (new in this phase) as `/etc/caddy/Caddyfile`, replacing the placeholder domain. Caddy issues and renews Let's Encrypt certificates automatically — no manual certbot steps. Verify:

```bash
curl -I https://admin.your-hotel-domain.com   # expect a valid cert, no browser warning
curl -I https://api.your-hotel-domain.com/health/live
```

Confirm no development artifacts are reachable in production: no `localhost` references baked into the frontend build (see §5's `NEXT_PUBLIC_API_BASE_URL` note), no port 3000/8000/5432 reachable from outside the host (§3's firewall requirement), `CORS_ALLOWED_ORIGINS` set to the exact real origin (never `*` — confirmed: nothing in `services/api/src` hardcodes a wildcard; the only value used is the env-driven one).

## 10. Migration Procedure

Covered by §6 for a fresh deploy. For an **existing** production database receiving a new release: `docker compose -f docker-compose.prod.yml up -d --build api` re-runs `alembic upgrade head` automatically before uvicorn binds (see the production Dockerfile's `CMD`). This is safe for a **single API instance** — if the pilot ever runs more than one API replica, move the migration step to a separate one-shot job outside the container's normal start path, since two containers racing `alembic upgrade head` against the same database is not something this setup has been tested against.

## 11. Initial Hotel Setup

| # | Step | Status |
|---|---|---|
| 1 | Provision server | MANUAL |
| 2 | Configure domain (DNS records) | MANUAL |
| 3 | Configure HTTPS (Caddy) | MANUAL (config file provided, §9) |
| 4 | Configure production environment (`.env`) | MANUAL (template provided, §5) |
| 5 | Create PostgreSQL database | AUTOMATED (`docker compose up -d postgres`) |
| 6 | Run migrations | AUTOMATED (runs on API container start) |
| 7 | Create initial tenant/hotel | **PARTIALLY AUTOMATED / real gap found this phase** — see below |
| 8 | Create restaurant | AUTOMATED (via API/admin-web, once step 7's user exists) |
| 9 | Create branch | AUTOMATED (via API/admin-web) |
| 10 | Create dining areas | AUTOMATED (via API/admin-web) |
| 11 | Create tables | AUTOMATED (via API/admin-web) |
| 12 | Configure roles | AUTOMATED (default role catalogue seeded automatically on tenant provisioning) |
| 13 | Create staff users | MANUAL (no bulk-import; one at a time via admin-web, fine at pilot scale) |
| 14 | Configure menu | AUTOMATED (via API/admin-web) |
| 15 | Configure recipes | AUTOMATED (via API/admin-web) |
| 16 | Configure inventory | AUTOMATED (via API/admin-web) |
| 17 | Generate QR codes | AUTOMATED (via API/admin-web, one call per table) |
| 18 | Run smoke test | AUTOMATED (`scripts/pilot_smoke_test.py`, fixed this phase — see §14) |
| 19 | Create manager account | Same mechanism as step 13 |
| 20 | Hand over system | MANUAL (User Manual / Quick Start Guide already exist) |

**Real gap found this phase, step 7:** `POST /api/v1/admin/tenants` (the only tenant-creation endpoint) is gated on `require_platform_admin`, which checks a `users.is_platform_admin` boolean that **no API call can set** — there is no self-service "become the first platform admin" path by design (confirmed via source: `admin_tenant_router.py`'s own docstring says "gated on `require_platform_admin`... `is_platform_admin=True`, not just some of them"). The only scripted paths that create such a user today are `services/api/scripts/seed_e2e_fixtures.py` and `services/api/scripts/backfill_tenant_owner.py`, and **both are explicitly test/support tooling, not production onboarding tools**:
- `seed_e2e_fixtures.py`'s own docstring says it's "used by apps/admin-web's Playwright E2E suite" but is "available for manual/CI use against any environment's `DATABASE_URL`" — with **hardcoded, publicly-known-in-this-repo credentials** (`e2e-admin@restaurantos.dev` / `E2EAdmin!2026`). It has no guard preventing it from being run against a real production database. This was reused for this phase's own disposable pilot validation (safe, throwaway environment) but **must never be run against the real production database** — doing so would create a platform-admin account with a password visible in this repo's own git history.
- `backfill_tenant_owner.py` requires a tenant and user to already exist and is meant for out-of-band support use, not first-time bootstrap.

**Recommendation (not implemented this phase — out of scope for deployment-readiness-only work per this phase's own instruction not to invent new functionality):** write a dedicated `bootstrap_platform_admin.py` that prompts for (or takes as CLI args) a real email and password, refuses to run if `APP_ENV=production` and a platform-admin user already exists, and never hardcodes credentials. Until that exists, the first hotel's platform-admin bootstrap on a real production database must be done by hand: connect directly to the production database and insert one `UserModel` row with `is_platform_admin=True`, following exactly the pattern `seed_e2e_fixtures.py` demonstrates (Argon2-hash a real, freshly-chosen password — never reuse the E2E one), then run `backfill_tenant_owner.py --apply` to grant that user Tenant Owner. This is a real, disclosed manual step, not a hidden landmine.

## 12. Backup

**Verified during Phase 1, not just described:** `pg_dump -F c` of a fully-migrated schema → `pg_restore` into a fresh database → confirmed identical table count (56) and `alembic_version` (`0010`) on the restored copy. Real backup, real restore, real verification.

- **Script:** `infrastructure/scripts/backup_postgres.sh` (new this phase) — runs `pg_dump` inside the Postgres container, fails loudly on a zero-byte dump rather than silently "succeeding," retains 14 days by default.
- **Schedule:** cron, nightly: `0 3 * * * /opt/restaurantos/infrastructure/scripts/backup_postgres.sh` (set `DATABASE_USER`/`DATABASE_PASSWORD`/`DATABASE_NAME`/`BACKUP_DIR` in the crontab or an env file it sources).
- **Retention:** 14 days on-host by default (`RETENTION_DAYS` env var).
- **Off-host copy — explicitly NOT yet wired up.** A same-host-only backup doesn't survive that host's own failure (disk death, provider incident). Before go-live, append an off-host step (rclone to an S3-compatible bucket, Backblaze B2, or scp to a second machine) to `backup_postgres.sh` — deliberately left as a placeholder rather than guessing at a provider you haven't chosen.

## 13. Restore

**Verified during Phase 1**, same test as §12. Procedure: `infrastructure/scripts/restore_postgres.sh <dump-file>` (new this phase) — drops and recreates the target database, restores, requires interactive `yes` confirmation unless `CONFIRM=yes` is set (for scripted DR drills only). Verify success with `SELECT version_num FROM alembic_version;` — should read the same head revision the backup was taken at.

## 14. Smoke Testing

`services/api/scripts/pilot_smoke_test.py` and `docs/RestaurantOS_Pilot_Deployment_Checklist.md` were reviewed against current `develop` and **two real bugs were found and fixed** (not just reviewed):

1. **QR verification (checklist item 14) always failed** when actually exercised with a real `--qr-token` — the script assumed the standard `{success, data, meta}` response envelope every other endpoint uses, but `GET /api/v1/qr/{token}` deliberately returns a flat, unwrapped `{tenant_id, branch_id, table_id}` body per ADR 0001 (confirmed in `qr_resolution_schemas.py`'s own docstring — a genuinely different, documented contract for this one unauthenticated bootstrap route, not a bug in the API). Fixed the script to match the real, intentional shape.
2. **Alembic check (item 3) failed with "not on PATH"** when the script is run via `path/to/venv/python.exe pilot_smoke_test.py` rather than an activated venv, because a bare `["alembic", ...]` subprocess call doesn't inherit that venv's own `Scripts/`/`bin/` directory. Fixed to use `[sys.executable, "-m", "alembic", ...]`, which always resolves to the same environment already running the script.

**Full run against a disposable, freshly-provisioned pilot environment** (real restaurant, branch, 3 dining areas — Indoor/Outdoor/Rooftop, 7 tables, food+drinks menu, a recipe, inventory with real opening stock, 2 QR codes): **14 of 14 executable automated checks passed, 0 failed**, including the exact Run 4 regression check (item 18 — automatic table release with no manual status call) and the OpenAPI-staleness check (item 7 — the one that would have caught Run 4's original incident). The 5 checklist items that are inherently manual (4, 6, 20, 21, 22) are unchanged — see the checklist doc itself.

## 15. Troubleshooting

- **API returns 500s immediately after deploy:** almost always a missing/wrong `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` or `DATABASE_URL` — check container logs (`docker compose -f docker-compose.prod.yml logs api`); Settings validation fails fast with a clear Pydantic error naming the missing field.
- **Guest QR ordering fails with a CORS error in the browser console:** `CORS_ALLOWED_ORIGINS` doesn't exactly match the origin the request came from (scheme + host + port, no trailing slash). Check it matches `https://admin.your-hotel-domain.com` exactly.
- **Frontend shows stale API behavior after a backend fix:** the frontend's `NEXT_PUBLIC_API_BASE_URL` is baked in at build time, not read at runtime — this symptom means the *backend* is fine but the frontend was never rebuilt, not the reverse.
- **"stale backend serving old code" (the Run 4 class of incident):** run item 7 of the smoke test (`pilot_smoke_test.py`) — it fetches the live `/openapi.json` and checks it against what current source code actually defines. This is the check that exists specifically because this exact incident happened once already.
- **Suspiciously many tables stuck `occupied`:** run item 12/18 of the smoke test; if item 18 (automatic release) fails specifically, treat it as the same P0 class Run 4 found — do not proceed until re-checked against fresh code (item 7).

## 16. Updating RestaurantOS

No image registry or CD pipeline exists yet (`RELEASE_CHECKLIST.md`'s own disclosed gap, still true). Today's update procedure is a manual rebuild-in-place:

```bash
cd /opt/restaurantos && git pull origin develop
docker compose -f docker-compose.prod.yml up -d --build api   # rebuilds image, re-runs migrations, restarts
cd apps/admin-web && npm ci && npm run build
sudo systemctl restart restaurantos-web
# Then: run scripts/pilot_smoke_test.py (see docs/RestaurantOS_Pilot_Deployment_Checklist.md)
```

Run the smoke test (§14) after every update, not just at initial go-live — this is the checklist's own stated purpose.

## 17. Rollback Procedure

1. **Application code:** `git checkout <previous-known-good-commit>`, then repeat §16's rebuild steps. There is no image tagging/registry yet, so "rollback" means rebuilding from an older commit, not swapping a pre-built image — slower than ideal, disclosed as a real limitation, not hidden.
2. **Database migration:** `docker compose -f docker-compose.prod.yml exec api alembic downgrade -1` to step back one migration — **verified working** in both directions during Phase 1 (§6), but only run this if the most recent migration is actually implicated in the incident; most incidents are code-only.
3. **Who decides:** name a specific on-call person before go-live — this guide cannot make that decision for you (Phase 1 Step 15's own boundary).
4. **Staff communication during rollback:** per the Pilot Deployment Checklist item 21 — tell staff to stop taking new orders and keep serving what's already fired, until the rollback completes and the smoke test passes again.

## 18. Security Checklist

Findings from a deployment-focused review this phase, each verified against the actual running code/config, not assumed:

| Check | Finding |
|---|---|
| Secrets not committed | ✅ `.gitignore` correctly excludes `.env`, `.env.*` (except `.env.example`), and the dev JWT `.pem` files. No hardcoded passwords/secrets found in `services/api/src` (grepped). |
| Production DEBUG disabled | ✅ No debug flag exists in the app at all — nothing to disable. `APP_ENV` itself is read but **does not currently gate any behavior** (confirmed: no `app_env == "development"` branches found anywhere in `services/api/src`) — worth knowing: setting `APP_ENV=production` is documentation/convention today, not an enforced safety switch. |
| CORS restricted | ✅ Fully env-driven (`CORS_ALLOWED_ORIGINS`), no wildcard anywhere in source; defaults to `localhost:3000` only if unset — **must** be set explicitly for production (§5). |
| JWT keys secure | ⚠️ No secrets manager exists yet; a root-only `.env` file is the current best option at this scale (disclosed, not silently accepted — see §5). |
| Database not publicly exposed | ✅ by design in `docker-compose.prod.yml` — Postgres binds `127.0.0.1:5432` only. |
| RLS enabled | ✅ Confirmed live: 48 of 56 tables have row-level security enabled after a clean migration. |
| Authentication enforced | ✅ Every route is Bearer-token-gated except a documented, deliberate allowlist (login/refresh/logout, the QR bootstrap route, and the guest-ordering routes, which re-verify the QR token as their only credential — see `main.py`'s own `_UNAUTHENTICATED_OPERATIONS` set). |
| Authorization enforced by backend | ✅ Confirmed live this phase: `is_platform_admin=True` does **not** bypass tenant-scoped RBAC checks (a fresh platform-admin bootstrap user got a real `403 PERMISSION_DENIED` on `restaurant.manage` until explicitly granted Tenant Owner). |
| No default passwords | ⚠️ **Real finding**: `seed_e2e_fixtures.py` creates a platform-admin account with a hardcoded, publicly-known (in this repo's own history) email/password, with no guard against being run against a real production database. Documented in §11; not fixed this phase (would be new tooling, out of this phase's scope) — **flagging clearly rather than silently leaving it undocumented**. |
| No test fixtures enabled in production | ⚠️ Same finding as above — `seed_e2e_fixtures.py` is *reachable* against production (it just needs `DATABASE_URL`), it is simply not *automatically run* there. The risk is operator error, not a live vulnerability. |
| No local development URLs | ✅ `NEXT_PUBLIC_API_BASE_URL` and `CORS_ALLOWED_ORIGINS` are both env-driven with no hardcoded `localhost` fallback used in production if set correctly (§5, §9). |
| No sensitive data in logs | Not independently re-audited this phase (out of the time this pass covered) — flagged as a residual gap, not claimed clean. |

## 19. Pilot Handover Checklist

Before the pilot's first real guest is served:
- [ ] All of §5's environment variables set with real, freshly-generated values (never anything from this repo's history or dev environment).
- [ ] Domain + HTTPS live and verified (§9).
- [ ] Backup cron job installed and has run at least once successfully (§12).
- [ ] Restore procedure known to at least one specific person (§13, §17).
- [ ] Platform-admin bootstrap done by hand per §11's disclosed gap, with a real, freshly-chosen password.
- [ ] Full smoke test (§14) run against the real production environment and passed.
- [ ] This smoke test's own test order/bill (§14) excluded from or annotated in the pilot's first-day reconciliation (Pilot Deployment Checklist item 22).
- [ ] Rollback owner named (§17).
- [ ] Staff handed the existing `docs/RestaurantOS_User_Manual.md` and `docs/RestaurantOS_Quick_Start_Guide.md`.

**This guide describes a disposable, locally-validated environment. No real server, domain, or DNS has been touched. Do not treat any step above as done until it has actually been performed against the real production target.**
