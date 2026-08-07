import { expect, test } from "@playwright/test"
import { createTenantViaUi, loginViaUi } from "./fixtures"

test.describe("Suspend Tenant", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page)
  })

  test("asks for confirmation, then suspends the tenant", async ({ page }) => {
    const displayName = await createTenantViaUi(page, "Suspend Flow")

    await page.getByRole("button", { name: "Suspend", exact: true }).click()
    const dialog = page.getByRole("alertdialog")
    await expect(dialog.getByRole("heading", { name: "Suspend this tenant?" })).toBeVisible()
    await expect(dialog.getByText(displayName, { exact: false })).toBeVisible()

    await page.getByRole("button", { name: "Suspend tenant" }).click()

    await expect(page.getByText("Tenant suspended.")).toBeVisible()
    await expect(page.getByText(/^suspended$/i)).toBeVisible()
    await expect(page.getByRole("button", { name: "Reactivate", exact: true })).toBeVisible()
    await expect(page.getByRole("button", { name: "Suspend", exact: true })).toHaveCount(0)
  })

  test("Cancel in the confirmation dialog leaves the tenant active", async ({ page }) => {
    await createTenantViaUi(page, "Suspend Cancel Flow")

    await page.getByRole("button", { name: "Suspend", exact: true }).click()
    await page.getByRole("button", { name: "Cancel" }).click()

    await expect(page.getByText(/^active$/i)).toBeVisible()
    await expect(page.getByRole("button", { name: "Suspend", exact: true })).toBeVisible()
  })

  test("appears in the list filtered to Suspended after suspending", async ({ page }) => {
    const displayName = await createTenantViaUi(page, "Suspend List Flow")
    await page.getByRole("button", { name: "Suspend", exact: true }).click()
    await page.getByRole("button", { name: "Suspend tenant" }).click()
    await expect(page.getByText("Tenant suspended.")).toBeVisible()

    await page.goto("/tenants")
    await page.getByRole("combobox", { name: "Filter by status" }).click()
    await page.getByRole("option", { name: /^suspended$/i }).click()

    await expect(page.getByRole("row", { name: new RegExp(displayName) })).toBeVisible()
  })
})
