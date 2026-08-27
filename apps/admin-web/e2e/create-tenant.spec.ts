import { expect, test } from "@playwright/test"
import { createTenantViaUi, loginViaUi, uniqueTenantName } from "./fixtures"

test.describe("Create Tenant", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page)
  })

  test("creates a tenant and redirects to its details page", async ({ page }) => {
    // Lowercase input on purpose -- confirms client-side upper-casing,
    // which createTenantViaUi()'s own default ("USD") wouldn't exercise.
    const displayName = await createTenantViaUi(page, "Create Flow", { currencyCode: "usd" })

    await expect(page.getByRole("heading", { name: displayName })).toBeVisible()
    await expect(page.getByText(/^active$/i)).toBeVisible()
    await expect(page.getByText("USD")).toBeVisible() // confirms client-side uppercasing worked
  })

  test("rejects an invalid currency code before calling the API", async ({ page }) => {
    const displayName = uniqueTenantName("Bad Currency Flow")

    await page.goto("/tenants/new")
    await page.getByLabel("Legal name").fill(`${displayName} LLC`)
    await page.getByLabel("Display name").fill(displayName)
    await page.getByLabel("Default currency").fill("US")
    await page.getByRole("button", { name: "Create tenant" }).click()

    await expect(page.getByText(/enter a 3-letter iso 4217/i)).toBeVisible()
    await expect(page).toHaveURL(/\/tenants\/new$/)
  })

  test("rejects a duplicate legal name via the API and shows an error toast", async ({
    page,
  }) => {
    // Real setup via the shared helper -- only the second (deliberately
    // failing) attempt below is what this test actually exercises.
    const displayName = await createTenantViaUi(page, "Duplicate Flow")

    await page.goto("/tenants/new")
    await page.getByLabel("Legal name").fill(`${displayName} LLC`)
    await page.getByLabel("Display name").fill(displayName)
    await page.getByLabel("Default currency").fill("USD")
    await page
      .getByLabel("Owner email")
      .fill(`${displayName.replace(/\s+/g, "-").toLowerCase()}-owner2@example.com`)
    await page.getByRole("button", { name: "Create tenant" }).click()

    await expect(page.getByText(/already exists/i)).toBeVisible()
    await expect(page).toHaveURL(/\/tenants\/new$/)
  })

  test("Cancel returns to the tenant list without creating anything", async ({ page }) => {
    await page.goto("/tenants/new")
    await page.getByRole("button", { name: "Cancel" }).click()
    await expect(page).toHaveURL(/\/tenants$/)
  })
})
