import { expect, test } from "@playwright/test"
import { createTenantViaUi, loginViaUi } from "./fixtures"

test.describe("Tenant Details", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page)
  })

  test("shows the tenant's fields and an Active tenant's Suspend action", async ({ page }) => {
    const displayName = await createTenantViaUi(page, "Details Flow")

    await expect(page.getByRole("heading", { name: displayName })).toBeVisible()
    await expect(page.getByText(`${displayName} LLC`)).toBeVisible() // legal name
    await expect(page.getByText("INR")).toBeVisible() // createTenantViaUi()'s own default
    await expect(page.getByRole("button", { name: "Suspend", exact: true })).toBeVisible()
    await expect(page.getByRole("button", { name: "Reactivate", exact: true })).toHaveCount(0)
    await expect(page.getByRole("button", { name: "Edit" })).toBeVisible()
  })

  test("breadcrumb link returns to the tenant list", async ({ page }) => {
    await createTenantViaUi(page, "Breadcrumb Flow")

    await page.getByRole("link", { name: "Tenants" }).click()

    await expect(page).toHaveURL(/\/tenants$/)
    await expect(page.getByRole("heading", { name: "Tenants" })).toBeVisible()
  })

  test("an unknown tenant id shows an error state with retry", async ({ page }) => {
    await page.goto("/tenants/00000000000000000000000000")

    await expect(page.getByRole("button", { name: "Retry" })).toBeVisible()
  })
})
