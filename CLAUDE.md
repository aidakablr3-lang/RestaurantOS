# RestaurantOS

## Before pushing to `develop`/`main`

Run these locally, in this order, before every push — CI (`.github/workflows/ci.yml`) runs the same checks and a round trip through a failed CI run costs more than running them first:

```bash
cd services/api
ruff format --check .   # catches formatting drift ruff check alone misses -- easy to forget, has caused a failed CI run before
ruff check .
python -m pytest tests/ -v   # needs TEST_DATABASE_URL for the integration half; skip that half only if no test Postgres is available

cd ../../apps/admin-web
npx tsc --noEmit
npx eslint .
npm run build
```

`mypy src/` (services/api) runs in CI too but is advisory/non-blocking (`continue-on-error: true` — pre-existing `DomainEvent` Protocol/ClassVar debt, see the job's own comment in `ci.yml`) — worth a glance for new errors, not a gate.

## Production deploys

Full runbook: `docs/DEPLOYMENT.md`. Read **§9 (Updating RestaurantOS)** before every deploy that includes a migration — specifically its warning that any migration adding a `CHECK`/`NOT NULL`/`UNIQUE` constraint needs an audit query run against production data *first*, or `api` crash-loops on a bad row (this has happened for real once already, migration 0015).

No SSH/DB access to the production host from this session — give the user exact commands to run themselves, never execute deploy/migration commands directly.
