import { expect, test } from "@playwright/test"
import { E2E_ADMIN, loginViaUi } from "./fixtures"

test.describe("Login", () => {
  test("signs in with valid credentials and lands on the tenant list", async ({ page }) => {
    await loginViaUi(page)

    await expect(page.getByRole("heading", { name: "Tenants" })).toBeVisible()
    await expect(page).toHaveURL(/\/tenants$/)
  })

  test("shows an error toast for the wrong password and stays on the login page", async ({
    page,
  }) => {
    await page.goto("/login")
    await page.getByPlaceholder("26-character ULID").fill(E2E_ADMIN.tenantId)
    await page.getByLabel("Email").fill(E2E_ADMIN.email)
    await page.getByLabel("Password").fill("definitely-the-wrong-password")
    await page.getByRole("button", { name: "Sign in" }).click()

    await expect(page.getByText(/invalid email or password/i)).toBeVisible()
    await expect(page).toHaveURL(/\/login$/)
  })

  test("rejects a malformed tenant id before it ever calls the API", async ({ page }) => {
    await page.goto("/login")
    await page.getByPlaceholder("26-character ULID").fill("too-short")
    await page.getByLabel("Email").fill(E2E_ADMIN.email)
    await page.getByLabel("Password").fill(E2E_ADMIN.password)
    await page.getByRole("button", { name: "Sign in" }).click()

    await expect(page.getByText(/26 characters/i)).toBeVisible()
    await expect(page).toHaveURL(/\/login$/)
  })

  test("unauthenticated access to the tenant list redirects to login", async ({ page }) => {
    await page.goto("/tenants")
    await expect(page).toHaveURL(/\/login$/)
  })
})
