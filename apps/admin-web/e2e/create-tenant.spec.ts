import { expect, test } from "@playwright/test"
import { createTenantViaUi, loginViaUi, uniqueTenantName } from "./fixtures"

test.describe("Create Tenant", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUi(page)
  })

  test("creates a tenant and redirects to its details page", async ({ page }) => {
    const displayName = await createTenantViaUi(page, "Create Flow")

    await expect(page.getByRole("heading", { name: displayName })).toBeVisible()
    await expect(page.getByText(/^active$/i)).toBeVisible()
    await expect(page.getByText("INR")).toBeVisible() // the form's own default flowed through
  })

  test("Default currency is a dropdown of real ISO 4217 codes, defaulting to INR", async ({
    page,
  }) => {
    // The bug this replaces: "GST" (a tax, not a currency) used to be
    // accepted through a free-text field checked only for "3 uppercase
    // letters". A dropdown can't produce that kind of invalid input at
    // all -- there's nothing left to "reject" at this layer, so this
    // test asserts the dropdown's own real behavior instead: it starts
    // on a real default and only ever offers real currencies.
    const displayName = uniqueTenantName("Currency Dropdown Flow")

    await page.goto("/tenants/new")
    await expect(page.getByRole("combobox", { name: "Default currency" })).toHaveText(
      /INR — Indian rupee/
    )

    await page.getByLabel("Legal name").fill(`${displayName} LLC`)
    await page.getByLabel("Display name").fill(displayName)
    await page.getByRole("combobox", { name: "Default currency" }).click()
    await page.getByRole("option", { name: "USD — United States dollar" }).click()
    await expect(page.getByRole("combobox", { name: "Default currency" })).toHaveText(
      /USD — United States dollar/
    )
    await page
      .getByLabel("Owner email")
      .fill(`${displayName.replace(/\s+/g, "-").toLowerCase()}-owner@example.com`)
    await page.getByRole("button", { name: "Create tenant" }).click()

    await page.getByRole("dialog", { name: "Tenant created" }).waitFor()
    await page.getByRole("button", { name: "Done" }).click()
    await page.waitForURL(/\/tenants\/[0-9A-Z]+$/)
    await expect(page.getByText("USD")).toBeVisible()
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
