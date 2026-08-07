import { expect, test } from "@playwright/test"
import { createTenantViaUi, loginViaUi } from "./fixtures"

async function createAndSuspend(page: import("@playwright/test").Page, prefix: string) {
  const displayName = await createTenantViaUi(page, prefix)
  await page.getByRole("button", { name: "Suspend", exact: true }).click()
  await page.getByRole("button", { name: "Suspend tenant" }).click()
  await expect(page.getByText("Tenant suspended.")).toBeVisible()
  return displayName
}

test.describe("Reactivate Tenant", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page)
  })

  test("asks for confirmation, then reactivates a suspended tenant", async ({ page }) => {
    const displayName = await createAndSuspend(page, "Reactivate Flow")

    await page.getByRole("button", { name: "Reactivate", exact: true }).click()
    const dialog = page.getByRole("alertdialog")
    await expect(dialog.getByRole("heading", { name: "Reactivate this tenant?" })).toBeVisible()
    await expect(dialog.getByText(displayName, { exact: false })).toBeVisible()

    await page.getByRole("button", { name: "Reactivate tenant" }).click()

    await expect(page.getByText("Tenant reactivated.")).toBeVisible()
    await expect(page.getByText(/^active$/i)).toBeVisible()
    await expect(page.getByRole("button", { name: "Suspend", exact: true })).toBeVisible()
    await expect(page.getByRole("button", { name: "Reactivate", exact: true })).toHaveCount(0)
  })

  test("Cancel in the confirmation dialog leaves the tenant suspended", async ({ page }) => {
    await createAndSuspend(page, "Reactivate Cancel Flow")

    await page.getByRole("button", { name: "Reactivate", exact: true }).click()
    await page.getByRole("button", { name: "Cancel" }).click()

    await expect(page.getByText(/^suspended$/i)).toBeVisible()
    await expect(page.getByRole("button", { name: "Reactivate", exact: true })).toBeVisible()
  })

  test("a full suspend-then-reactivate round trip is reflected in the list", async ({
    page,
  }) => {
    const displayName = await createAndSuspend(page, "Round Trip Flow")

    await page.getByRole("button", { name: "Reactivate", exact: true }).click()
    await page.getByRole("button", { name: "Reactivate tenant" }).click()
    await expect(page.getByText("Tenant reactivated.")).toBeVisible()

    await page.goto("/tenants")
    await page.getByRole("combobox", { name: "Filter by status" }).click()
    await page.getByRole("option", { name: /^active$/i }).click()
    await expect(page.getByRole("row", { name: new RegExp(displayName) })).toBeVisible()
  })
})
