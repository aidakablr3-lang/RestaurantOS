/**
 * Verifies the backend (services/api) is reachable and the fixed E2E
 * platform-admin fixture exists before any spec runs, so a
 * misconfigured environment fails fast with one clear message instead
 * of 20 confusing per-test failures.
 *
 * This suite does not start Postgres or services/api itself -- doing so
 * needs a real database, migrations, and Python, which is out of scope
 * for a Node-based test runner. See apps/admin-web/e2e/README.md for
 * the one-time setup.
 */
import { E2E_ADMIN, apiBaseUrl } from "./fixtures"

export default async function globalSetup() {
  if (!E2E_ADMIN.tenantId) {
    throw new Error(
      "E2E_ADMIN_TENANT_ID is not set. Run 'python scripts/seed_e2e_fixtures.py' from " +
        "services/api (against the database your backend is using), then export " +
        "E2E_ADMIN_TENANT_ID with the tenantId it prints. See apps/admin-web/e2e/README.md."
    )
  }

  const base = apiBaseUrl()

  let loginResponse: Response
  try {
    loginResponse = await fetch(`${base}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tenantId: E2E_ADMIN.tenantId,
        email: E2E_ADMIN.email,
        password: E2E_ADMIN.password,
      }),
    })
  } catch (cause) {
    throw new Error(
      `Could not reach services/api at ${base}. Is the backend running? ` +
        `See apps/admin-web/e2e/README.md for setup.`,
      { cause }
    )
  }

  if (!loginResponse.ok) {
    throw new Error(
      `services/api rejected the E2E platform-admin login (HTTP ${loginResponse.status}). ` +
        `Run 'python scripts/seed_e2e_fixtures.py' from services/api against the same ` +
        `database this backend is using, then retry. See apps/admin-web/e2e/README.md.`
    )
  }
}
