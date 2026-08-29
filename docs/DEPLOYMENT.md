# RestaurantOS — Deployment Runbook

**Target:** Ubuntu 24.04, single node. Written for an original 2 vCPU / 6GB / 150GB plan; actually deployed on an AWS Lightsail instance in Mumbai, 2 vCPU / 4GB RAM / 80GB disk, static IP `13.126.148.121` — `01_server_setup.sh` adds a 2GB swapfile specifically because of the smaller RAM (the stack runs fine at idle in 4GB, but the `admin-web` image's `next build` step is memory-hungry enough to risk an OOM kill without headroom).
**Domains:** `api.prashanthai.com`, `admin.prashanthai.com` — DNS on Cloudflare, A records **DNS-only** (grey cloud, not proxied — Caddy needs to see the real client IP and handle its own TLS via Let's Encrypt HTTP-01/TLS-ALPN challenges, which Cloudflare's proxy would interfere with).

**Status as of this writing:** live. All four `scripts/deploy/` steps have been run against the real box, in order, output reviewed at each step. HTTPS is live on both domains through Caddy. Platform admin bootstrapped. Backup → scratch-database restore → per-table row-count comparison has been run and passed. A direct connection attempt to port 5432 from off the box timed out, confirming Postgres is unreachable from outside. See §13 for the current state of the security checklist.

---

## 1. Architecture

```
Internet
   |  HTTPS (80/443 only)
   v
Caddy (docker-compose.prod.yml, automatic Let's Encrypt TLS)
   |                              |
   v                              v
admin-web:3000                 api:8000
(Next.js, Docker,              (FastAPI, Docker,
 standalone build)               migrations run on start)
                                   |
                                   v
                             postgres:5432
                             (Docker, named volume,
                              NO host port published)
```

All four services run in `docker-compose.prod.yml`, on Compose's own default project network. Only Caddy publishes anything to the host (`80`/`443`); `postgres`, `api`, and `admin-web` publish **no host ports at all** — reachable only by sibling containers, by service name.

This is a deliberate change from an earlier draft of this deployment, which ran Caddy and admin-web directly on the host (via `systemd` + `next start`) and bound Postgres/API to `127.0.0.1`. Containerizing all four services here means Postgres is reachable from nowhere outside the Compose network — not even the host's own loopback — and `docker compose up -d --build` is the entire update procedure (§9), not two separate tracks.

## 2. Prerequisites

- Ubuntu 24.04, 2 vCPU / 6GB RAM / 150GB disk (the target this runbook is written for).
- `git` access to this repository.
- Cloudflare DNS control for `prashanthai.com`, ready to add two A records, **DNS-only** (not proxied).
- A real email address for Let's Encrypt expiry/problem notices (never published — see §5).
- A real email address for the first platform-admin login (see §7).

Nothing else needs to pre-exist on the box — `scripts/deploy/01_server_setup.sh` installs Docker itself.

## 3. What I need from you before this can run

Listed once here, not scattered through the steps below:

1. **DNS**: two Cloudflare A records, DNS-only (grey cloud):
   - `api.prashanthai.com` → the VPS's public IPv4
   - `admin.prashanthai.com` → the VPS's public IPv4
2. **ACME email** — a real address Let's Encrypt can send certificate expiry/problem notices to. Passed to `scripts/deploy/02_generate_secrets.sh --acme-email` (or `deploy.sh --acme-email`).
3. **Platform-admin email** — the real email the first platform-admin account should use. Passed to `scripts/deploy/04_bootstrap_platform_admin.sh` (or `deploy.sh --admin-email`). Its password is generated on the box and printed once during that step — nowhere else.
4. **The VPS itself** (root/sudo SSH access) — pending KYC approval per your own note.

Nothing else is required from you. No secret is ever asked for in chat or committed to this repository — everything else is generated on the box by `scripts/deploy/02_generate_secrets.sh`.

## 4. Deploy sequence

Run as root (or via sudo), from a fresh box. Each script is idempotent-safe to re-run individually (each has its own guard against clobbering existing state); `deploy.sh` chains all four for the "single run" case.

```bash
git clone <repo-url> /opt/restaurantos
cd /opt/restaurantos

# Either the orchestrated single run:
bash scripts/deploy/deploy.sh --acme-email you@prashanthai.com --admin-email you@prashanthai.com

# ...or the four steps individually, in order:
bash scripts/deploy/01_server_setup.sh
bash scripts/deploy/02_generate_secrets.sh --acme-email you@prashanthai.com
bash scripts/deploy/03_migrate.sh
bash scripts/deploy/04_bootstrap_platform_admin.sh you@prashanthai.com
```

What each does — see each script's own header comment for the full reasoning:

| # | Script | Does |
|---|--------|------|
| 1 | `01_server_setup.sh` | `ufw` (22/80/443 only), `fail2ban` (sshd jail), `unattended-upgrades`, installs Docker Engine + Compose plugin |
| 2 | `02_generate_secrets.sh` | Generates `DATABASE_PASSWORD` (`openssl rand`) and a fresh RS256 JWT keypair (`openssl genrsa`/`openssl rsa`) **on this box**, writes `/opt/restaurantos/.env` (`chmod 600`). Refuses to overwrite an existing `.env`. |
| 3 | `03_migrate.sh` | Builds the `api` image, starts `postgres`, waits for it healthy, runs `alembic upgrade head` explicitly (isolated from the api container's own start sequence, for a clear failure point), verifies `alembic current == alembic heads` |
| 4 | `04_bootstrap_platform_admin.sh` | Starts `postgres`/`api`/`admin-web`, dry-runs `bootstrap_platform_admin.py` for review, asks for a typed `yes`, then `--apply`s it — creates the **first** platform-admin account (refuses if one already exists anywhere in the database) |

After step 4, everything except Caddy is running. Caddy is deliberately **not** started by these scripts — it needs DNS live first (§5).

## 5. DNS + HTTPS

1. Add the two Cloudflare A records from §3, DNS-only.
2. Confirm they've propagated: `dig +short api.prashanthai.com` / `dig +short admin.prashanthai.com` should return the VPS's IP.
3. If you left `CADDY_ACME_EMAIL` as the placeholder during step 2 above, edit it now in `/opt/restaurantos/.env`.
4. Start Caddy:
   ```bash
   cd /opt/restaurantos
   docker compose -f docker-compose.prod.yml up -d caddy
   ```
5. Verify:
   ```bash
   curl -I https://admin.prashanthai.com
   curl -I https://api.prashanthai.com/health/live
   ```
   Both should return a valid certificate (no browser/curl TLS warning) within a minute or two of Caddy starting — it issues Let's Encrypt certificates automatically on first request per domain.

Confirm no development artifacts are reachable: `curl` for ports 3000/5432/8000 directly against the VPS's public IP should all **time out or refuse** (`ufw` blocks everything but 22/80/443 at the host firewall, and postgres/api/admin-web publish no host ports at all regardless — two independent layers, not one).

## 6. First platform-admin login → first real tenant

Step 4 above printed (once, not stored anywhere):

```
tenantId for login: <ULID>
Email:    you@prashanthai.com
Generated password (shown once, not stored or logged): <password>
```

Save these somewhere you trust immediately — they are never shown again.

```bash
curl -X POST https://api.prashanthai.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"tenantId": "<ULID from above>", "email": "you@prashanthai.com", "password": "<password from above>"}'
```

Use the resulting `accessToken` as a Bearer token against `POST /api/v1/admin/tenants` to create the first real hotel/restaurant tenant. From there, `services/api/scripts/create_user.py` (already in this repo) creates that tenant's first Owner — see its own docstring; it's the same operator-script pattern as the platform-admin bootstrap, needed for exactly one case the real API can't cover: a tenant's very first user, before anyone holds `roles.assign` yet.

## 7. Environment variables

All of these live in one file: `/opt/restaurantos/.env`, written by `scripts/deploy/02_generate_secrets.sh`. `docker-compose.prod.yml` reads it automatically (Compose's standard `.env`-in-the-compose-file's-directory behavior) and passes each value through to whichever service needs it — `api` at container start (read from real environment variables, not a mounted file — `DatabaseSettings`/`JWTSettings` don't inherit `Settings`' own `env_file=".env"` config, a documented pre-existing gap; Compose's env-var passthrough is unaffected by this and handles it correctly), `admin-web` as a **build** arg (Next.js bakes `NEXT_PUBLIC_*` values into the client bundle at `next build` time, not at container start — changing it needs `--build`, not just a restart), `caddy` as a runtime environment variable it substitutes into the Caddyfile via `{$CADDY_ACME_EMAIL}`.

| Variable | Consumed by | Generated by | Notes |
|---|---|---|---|
| `APP_ENV` | api | `02_generate_secrets.sh` (literal `production`) | Documentation/convention today — confirmed nothing in `services/api/src` branches on it |
| `DATABASE_USER` / `DATABASE_NAME` | postgres, api | `02_generate_secrets.sh` (literal `restaurantos`) | Postgres role/db name, not tenant-related |
| `DATABASE_PASSWORD` | postgres, api | `02_generate_secrets.sh` (`openssl rand -base64 32`) | Never reused across environments |
| `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` | api | `02_generate_secrets.sh` (`openssl genrsa`/`openssl rsa`) | Full PEM content, real deployment-specific keypair — never the dev keypair in `infrastructure/docker/dev-jwt/` or anything from this repo's git history |
| `CORS_ALLOWED_ORIGINS` | api | `02_generate_secrets.sh` (literal `https://admin.prashanthai.com`) | Must match the admin origin exactly — no wildcard is accepted anywhere in source |
| `NEXT_PUBLIC_API_BASE_URL` | admin-web (build arg) | `02_generate_secrets.sh` (literal `https://api.prashanthai.com`) | Baked in at image build time |
| `CADDY_ACME_EMAIL` | caddy | You, via `--acme-email` (or edited into `.env` afterward) | Let's Encrypt notices only, never published |

`apps/admin-web/.env.local.example` and `services/api/.env.example` are for **local, non-Docker development only** — this production deploy doesn't read either; `docker-compose.prod.yml` sources everything from the one root `.env`.

## 8. Backup and restore

- **Backup:** `scripts/deploy/backup.sh` — `pg_dump` run inside the `postgres` container (no host port needed, matches §1's "reachable only inside Compose" design), then uploaded to S3 (below). Fails loudly on a zero-byte dump *or* a failed upload — a silent off-host failure is worse than no backup, since it looks like it's working when it isn't. Install as a nightly cron job (as root, since `.env` is root-only and the job needs Docker access):
  ```bash
  sudo crontab -e
  ```
  Add:
  ```cron
  0 3 * * * bash -c 'cd /opt/restaurantos && set -a && . .env && set +a && BACKUP_DIR=/var/backups/restaurantos RETENTION_DAYS=7 bash scripts/deploy/backup.sh' >> /var/log/restaurantos-backup.log 2>&1
  ```
  Confirm it's actually scheduled, not just saved: `sudo crontab -l` should show the line, and `systemctl is-active cron` should read `active`.

  Retains 7 days on-host (`RETENTION_DAYS`); S3 retention is a **bucket lifecycle rule** (30 days), not script logic — it keeps pruning even if this box is down.

- **Off-host copy (S3):** every dump is uploaded to a dedicated bucket immediately after a successful local dump. Set up once, per deployment:
  1. **S3 bucket** — e.g. `restaurantos-backups-prashanthai`, region `ap-south-1` (same region as the instance). Enable **versioning**. Block all public access (default). Enable default (SSE-S3) encryption.
  2. **Lifecycle rule** on that bucket — expire (permanently delete) current versions 30 days after creation; also expire noncurrent versions and delete expired object markers, for tidiness (this workflow never overwrites a key, so noncurrent versions shouldn't normally accumulate — versioning here is mainly a safety net against accidental/malicious overwrite).
  3. **IAM user** — programmatic access only, no console login. Attach this inline policy (replace `BUCKET_NAME`):
     ```json
     {
         "Version": "2012-10-17",
         "Statement": [
             {
                 "Sid": "RestaurantOSBackupWriteOnly",
                 "Effect": "Allow",
                 "Action": "s3:PutObject",
                 "Resource": "arn:aws:s3:::BUCKET_NAME/*"
             }
         ]
     }
     ```
     `s3:PutObject` only — no `ListBucket`, no `GetObject`, no `DeleteObject`, scoped to exactly one bucket ARN. If this box is compromised, whoever has this credential still can't read or destroy a single backup, past or future. Generate an access key for this user.
  4. Add `S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` to `/opt/restaurantos/.env` (see `.env.production.example`) — edit the file directly on the box (`sudo nano /opt/restaurantos/.env`) rather than pasting long-lived AWS credentials through any chat session; unlike the one-time platform-admin password, these are reusable and would need active rotation if ever exposed.

  **Restoring from S3 needs a *different*, read-capable credential** — this write-only IAM user structurally cannot download anything back, by design. Use your own AWS console login or a separate CLI profile with read access to pull a dump down, then run `restore.sh` on it as usual.

- **Restore:** `scripts/deploy/restore.sh <dump-file>` — drops and recreates the target database, restores, then **automatically verifies**: the restored `alembic_version` matches `alembic heads` for the code currently deployed, and the restored database has at least one table. Exits non-zero and prints `RESTORE VERIFICATION FAILED` if either check fails, rather than reporting success on a wrong or empty restore. Requires interactive `yes` confirmation (`CONFIRM=yes` bypasses it, for scripted DR drills only). `DATABASE_NAME` can point at a scratch database name instead of the real one — the dump itself carries no fixed target — for a non-destructive restore drill.
- **Row-count verification:** `scripts/deploy/compare_row_counts.sh <source-db> <target-db>` — `restore.sh`'s own checks confirm the right *tables* and migration head exist, not that every row actually came back. This compares every table's row count between two databases in the same Postgres container and fails loudly on any mismatch. Run it after a scratch restore, comparing the live database against the scratch one:
  ```bash
  DATABASE_USER=restaurantos DATABASE_PASSWORD=<from .env> \
      ./scripts/deploy/compare_row_counts.sh restaurantos restaurantos_scratch_verify
  ```

Know who is authorized to run a restore, and rehearse it at least once against a disposable copy before you need it for real.

## 9. Updating RestaurantOS

Containerizing admin-web collapses what used to be two separate update tracks (Docker rebuild for the API, `npm run build` + `systemctl restart` for the frontend) into one:

```bash
cd /opt/restaurantos && git pull origin develop
docker compose -f docker-compose.prod.yml up -d --build api admin-web
```

This rebuilds both images and restarts them; migrations re-run automatically (`api`'s own `CMD`) before it starts serving. `postgres` and `caddy` are untouched by this command. Run the smoke test (§10) after every update, not just at initial go-live.

No image registry or CD pipeline exists yet — this is a manual rebuild-in-place, same disclosed limitation the project has had since the first pilot draft.

**Any migration that adds a `CHECK`/`NOT NULL`/`UNIQUE` constraint must be preceded by an audit query against production data**, run and reviewed *before* `git pull`. `api` runs `alembic upgrade head` on every container start — if a new constraint rejects a row that already exists, the migration fails, the container exits, Docker restarts it, and it fails again, crash-looping until someone notices and fixes the offending row(s) by hand. (This happened live: migration 0015 added a `CHECK` on `tenants.default_currency_code`, one existing tenant had an invalid value, and `api` crash-looped for ~10 minutes before it was caught.) Write the audit query from the migration's own new constraint condition, negated, and run it against production before applying the migration — not after a crash-loop reveals the problem.

## 10. Rollback

1. **Application code:** `git checkout <previous-known-good-commit>`, then repeat §9's rebuild.
2. **Database migration:** `docker compose -f docker-compose.prod.yml exec api python -m alembic downgrade -1` — only if the most recent migration is actually implicated; most incidents are code-only.
3. **Who decides:** name a specific on-call person before go-live — this runbook cannot make that decision for you.

## 11. Smoke testing

`services/api/scripts/pilot_smoke_test.py` walks a real order → kitchen → payment → EOD cycle against a live deployment. Run it after every deploy and every update, from inside the `api` container (it needs to reach both the API and the database directly):

```bash
docker compose -f docker-compose.prod.yml exec api python scripts/pilot_smoke_test.py \
    --base-url http://localhost:8000 \
    --database-url "$DATABASE_URL" \
    --tenant-id <tenant ULID from §6> \
    --branch-id <branch ULID> \
    --table-id <an 'available' table's ULID> \
    --email <a staff email that can log in> \
    --password <that account's password>
```

`--database-url "$DATABASE_URL"` reuses the api container's own real connection string (already set as a real environment variable inside it) — the script's alembic-state check is silently skipped if this flag is omitted. This needs a real tenant/branch/table/staff account to exercise, so run it against the first real tenant created in §6, not the platform-ops bootstrap tenant (which has no restaurant, branch, or tables at all).

## 12. Troubleshooting

- **API returns 500s immediately after deploy:** almost always a missing/wrong `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` or `DATABASE_URL` — check `docker compose -f docker-compose.prod.yml logs api`; Settings validation fails fast with a clear Pydantic error naming the missing field.
- **Guest QR ordering fails with a CORS error:** `CORS_ALLOWED_ORIGINS` doesn't exactly match the requesting origin (scheme + host, no trailing slash, no port since 443 is implicit). Should be exactly `https://admin.prashanthai.com`.
- **Frontend shows stale API behavior after a backend fix:** `NEXT_PUBLIC_API_BASE_URL` and every other `NEXT_PUBLIC_*` value are baked in at build time — this means the backend is fine but `admin-web` was never rebuilt (§9), not the reverse.
- **Caddy won't issue a certificate:** almost always DNS not actually pointing at this host yet, or a Cloudflare record still proxied (orange cloud) instead of DNS-only — Let's Encrypt's HTTP-01/TLS-ALPN challenges need to reach this host directly. `docker compose -f docker-compose.prod.yml logs caddy` shows the exact ACME error.
- **`04_bootstrap_platform_admin.sh` reports a platform admin already exists:** working as designed — it refuses to create a second one. If you genuinely need to recover access, use `services/api/scripts/create_user.py` against the existing platform-ops tenant, or reset the existing account's password directly (no self-service password-reset endpoint exists yet — a known gap, not specific to this deploy).

## 13. Security checklist

| Check | Status |
|---|---|
| Postgres never exposed to the internet | ✅ by construction — no `ports:` entry at all in `docker-compose.prod.yml`, not even loopback-bound |
| No secret committed | ✅ `.gitignore` excludes `.env`/`.env.*` (except `.example` files); every secret in this deploy is generated on the box by `02_generate_secrets.sh`, never typed into chat or a commit |
| Firewall restricts to 22/80/443 | ✅ `01_server_setup.sh` (`ufw default deny incoming`) |
| Brute-force protection on SSH | ✅ `01_server_setup.sh` (`fail2ban`, sshd jail) |
| OS security patches applied automatically | ✅ `01_server_setup.sh` (`unattended-upgrades`) |
| CORS restricted, no wildcard | ✅ env-driven, `https://admin.prashanthai.com` only — confirmed no wildcard accepted anywhere in `services/api/src` |
| RLS enforced | ✅ per-tenant tables carry RLS policies scoped by `app.tenant_id`; confirmed structurally by `bootstrap_platform_admin.py`'s own need to loop per-tenant rather than query `users` directly with no tenant context |
| First platform-admin account has no hardcoded credential | ✅ `bootstrap_platform_admin.py` takes a real email, generates or accepts a real password, refuses to run if one already exists — unlike `seed_e2e_fixtures.py`, which has a hardcoded, publicly-known password and must never be run against this database |
| Automated backups | ✅ `backup.sh`, nightly cron (§8), with an S3 off-host copy uploaded immediately after every local dump — fails loudly if either half fails |
| Off-host backup credential can't read or destroy backups | ✅ the S3 IAM user is `s3:PutObject`-only on one bucket — no `ListBucket`/`GetObject`/`DeleteObject`, no other buckets. A compromised box inherits this same credential and still can't touch existing backups |
| Automated restore verification | ✅ `restore.sh` checks `alembic_version` and table count automatically, `compare_row_counts.sh` checks every table's row count against the source, both fail loudly rather than reporting a false success |

## 14. Correcting bad billing data

`order_tax_lines` and `bill_adjustments` are append-only by design (see their own model docstrings) — nothing in the app ever edits a historical charge in place, and a manual `UPDATE` against either would falsify what was actually charged and destroy the audit trail. When a bill was generated with wrong data (e.g. a mis-entered tax rate — see the `taxes.rate` incident this section grew out of), which remediation is correct depends on whether real money was involved, not on how the bug happened to be found:

- **A real customer was billed and has (or may have) paid**: apply a `write_off` `BillAdjustment` for the excess (`POST /api/v1/bills/{id}/adjustments`, or the "Apply adjustment" dialog on the bill's admin-web page) if the bill is still `open`/`partially_paid`, or a `Refund` against the settled `Payment` if it's already `closed`. Either way this is the only correct path — it corrects the amount owed/refunded while leaving a truthful record that a real charge was made and then corrected. Never delete a bill a real customer was ever shown or charged against.
- **No real customer, no payment** (test data, a smoke-test order, a rehearsal): a `write_off` here would be false — it records a charge-then-forgiveness that never happened, permanently, in reports and the audit trail. Delete the order and bill outright instead. Correct test **only when**: `bills.status != 'closed'` **and** zero rows exist in `payments` for that bill (not just zero *settled* ones — an `authorized`/`captured`-but-not-yet-`settled` payment means a real transaction is in flight even if money hasn't fully landed). If either doesn't hold, treat it as real money and use the write-off/refund path above instead.

Deleting an order/bill means deleting every row that references it first — every relevant FK in this schema is `ON DELETE RESTRICT`, so a direct `DELETE FROM orders` fails outright otherwise. Dependency order, leaves first:

```
refunds → kitchen_items → bill_adjustments → payments → kitchen_tickets → order_tax_lines → order_items → bills → orders
```

(`refunds` references both `payments.id` and `orders.id`; `kitchen_items` references both `kitchen_tickets.id` and `order_items.id`.) Enumerate every row that exists for the specific order/bill first — don't assume the shape (a production incident's own audit found an order already `closed` via a standalone `close_order` action with zero payments, not the payment-triggered close path one might assume) — then delete inside a single `BEGIN; ... COMMIT;` transaction scoped by `order_id`/`bill_id`, so a missed dependency rolls back everything instead of leaving orphaned rows.

## 15. Invoice numbering — known limitation: no void/credit-note concept

`Bill.invoice_number` (migration `0019`) is a GST-compliant sequential series (`{invoice_prefix}/{FY}/{seq:06d}`, per branch, reset each 1 April IST) allocated once, atomically, the moment a bill with a `gstin`'d branch is generated. It is never reused and never reassigned to a different bill.

`Bill.status` has **no `voided` state**, and there is **no credit-note concept anywhere in this schema**. If a numbered invoice needs to be cancelled after the fact, this deployment currently has no compliant way to do it — the §14 delete path only applies to bills with zero payments and is not a substitute for voiding a bill that already carries a real invoice number a customer may have seen. Do not repurpose the delete path for a numbered invoice. This is deliberately unbuilt pending confirmation from the business's CA on whether Indian GST practice requires a credit note, a formal void flag, or something else — treat any numbered-invoice cancellation as blocked until that's designed.

---

**Status:** deployed to the real target (Lightsail, Mumbai, `13.126.148.121`, `api.prashanthai.com` / `admin.prashanthai.com`) — all four `scripts/deploy/` steps run and verified against the real box, HTTPS live, platform admin bootstrapped, backup → scratch-restore → row-count check proven, Postgres confirmed unreachable from outside. This document is now describing a real, running deployment, not a rehearsal.
