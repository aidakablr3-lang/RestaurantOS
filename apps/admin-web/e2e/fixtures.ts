import type { Page } from "@playwright/test"

/**
 * Matches services/api/scripts/seed_e2e_fixtures.py exactly. Override
 * via env vars to point this suite at a different environment's already-
 * seeded fixture without touching code.
 */
export const E2E_ADMIN = {
  tenantId: process.env.E2E_ADMIN_TENANT_ID ?? "",
  email: process.env.E2E_ADMIN_EMAIL ?? "e2e-admin@restaurantos.dev",
  password: process.env.E2E_ADMIN_PASSWORD ?? "E2EAdmin!2026",
}

export function apiBaseUrl(): string {
  return process.env.E2E_API_BASE_URL ?? "http://localhost:8000"
}

/** Drives the real login form -- Login itself is one of the flows this
 * suite must cover, so every other spec's setup exercises it too rather
 * than bypassing it with an injected token. */
export async function loginViaUi(page: Page): Promise<void> {
  await page.goto("/login")
  await page.getByPlaceholder("26-character ULID").fill(E2E_ADMIN.tenantId)
  await page.getByLabel("Email").fill(E2E_ADMIN.email)
  await page.getByLabel("Password").fill(E2E_ADMIN.password)
  await page.getByRole("button", { name: "Sign in" }).click()
  await page.waitForURL("**/dashboard")
}

export function uniqueTenantName(prefix: string): string {
  return `${prefix} ${Date.now()}-${Math.floor(Math.random() * 10_000)}`
}

/** Drives the real Create Tenant form. Used as setup by specs (List,
 * Details, Edit, Suspend, Reactivate) that need a fresh tenant to act
 * on, rather than depending on whatever tenants a previous run left
 * behind. Returns the created tenant's display name, unique per call,
 * used to find it again in the list/details UI. Leaves the browser on
 * the new tenant's details page. */
export async function createTenantViaUi(page: Page, namePrefix: string): Promise<string> {
  const displayName = uniqueTenantName(namePrefix)
  await page.goto("/tenants/new")
  await page.getByLabel("Legal name").fill(`${displayName} LLC`)
  await page.getByLabel("Display name").fill(displayName)
  await page.getByLabel("Default currency").fill("USD")
  await page.getByRole("button", { name: "Create tenant" }).click()
  await page.waitForURL(/\/tenants\/[0-9A-Z]+$/)
  return displayName
}
