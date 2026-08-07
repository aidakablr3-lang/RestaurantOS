import { expect, test } from "@playwright/test"
import { createTenantViaUi, loginViaUi } from "./fixtures"

test.describe("Tenant List", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page)
  })

  test("shows a freshly created tenant with its status", async ({ page }) => {
    const displayName = await createTenantViaUi(page, "List Flow")

    await page.goto("/tenants")

    const row = page.getByRole("row", { name: new RegExp(displayName) })
    await expect(row).toBeVisible()
    await expect(row.getByText(/^active$/i)).toBeVisible()
  })

  test("filtering by status narrows the table", async ({ page }) => {
    const displayName = await createTenantViaUi(page, "Filter Flow")
    await page.goto("/tenants")

    await page.getByRole("combobox", { name: "Filter by status" }).click()
    await page.getByRole("option", { name: /^suspended$/i }).click()

    await expect(page.getByRole("row", { name: new RegExp(displayName) })).toHaveCount(0)

    await page.getByRole("combobox", { name: "Filter by status" }).click()
    await page.getByRole("option", { name: "All statuses" }).click()
    await expect(page.getByRole("row", { name: new RegExp(displayName) })).toBeVisible()
  })

  test("clicking a tenant navigates to its details page", async ({ page }) => {
    const displayName = await createTenantViaUi(page, "Nav Flow")
    await page.goto("/tenants")

    await page.getByRole("link", { name: displayName }).click()

    await expect(page).toHaveURL(/\/tenants\/[0-9A-Z]+$/)
    await expect(page.getByRole("heading", { name: displayName })).toBeVisible()
  })
})
