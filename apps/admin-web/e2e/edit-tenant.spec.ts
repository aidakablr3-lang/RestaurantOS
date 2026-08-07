import { expect, test } from "@playwright/test"
import { createTenantViaUi, loginViaUi } from "./fixtures"

test.describe("Edit Tenant", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page)
  })

  test("pre-fills the form from the current tenant", async ({ page }) => {
    // Regression coverage: Sprint 4.1 Step 3 found the edit form never
    // pre-filled at all (a broken React Hook Form `values` usage, fixed
    // by switching to defaultValues + useEffect + form.reset()). This is
    // the automated version of that manual finding.
    const displayName = await createTenantViaUi(page, "Edit Prefill Flow")

    await page.getByRole("button", { name: "Edit" }).click()

    await expect(page.getByLabel("Display name")).toHaveValue(displayName)
  })

  test("saves changes to display name and metadata", async ({ page }) => {
    await createTenantViaUi(page, "Edit Save Flow")
    const updatedName = `Renamed ${Date.now()}`

    await page.getByRole("button", { name: "Edit" }).click()
    await page.getByLabel("Display name").fill(updatedName)
    await page.getByLabel("Metadata").fill('{"neighborhood": "Uptown"}')
    await page.getByRole("button", { name: "Save changes" }).click()

    await page.waitForURL(/\/tenants\/[0-9A-Z]+$/)
    await expect(page.getByRole("heading", { name: updatedName })).toBeVisible()
    await expect(page.getByText(/"neighborhood"/)).toBeVisible()
    await expect(page.getByText(/"Uptown"/)).toBeVisible()
  })

  test("rejects malformed JSON metadata before calling the API", async ({ page }) => {
    await createTenantViaUi(page, "Edit Bad JSON Flow")

    await page.getByRole("button", { name: "Edit" }).click()
    await page.getByLabel("Metadata").fill("{not valid json")
    await page.getByRole("button", { name: "Save changes" }).click()

    await expect(page.getByText(/must be valid json/i)).toBeVisible()
  })

  test("Cancel returns to the tenant's details page without saving", async ({ page }) => {
    const displayName = await createTenantViaUi(page, "Edit Cancel Flow")

    await page.getByRole("button", { name: "Edit" }).click()
    await page.getByLabel("Display name").fill("Should not be saved")
    await page.getByRole("button", { name: "Cancel" }).click()

    await expect(page).toHaveURL(/\/tenants\/[0-9A-Z]+$/)
    await expect(page.getByRole("heading", { name: displayName })).toBeVisible()
  })
})
