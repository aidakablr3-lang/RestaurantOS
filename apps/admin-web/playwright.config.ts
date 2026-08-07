import { defineConfig, devices } from "@playwright/test"

const PORT = process.env.E2E_PORT ?? "3100"
const BASE_URL = process.env.E2E_BASE_URL ?? `http://localhost:${PORT}`

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // tests share one seeded tenant's data; keep them sequential
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  // "github" alone annotates the PR but writes no report to disk --
  // ci.yml's "Upload Playwright report" step needs the "html" reporter's
  // output to actually have something to upload on failure. `open:
  // "never"` avoids the html reporter trying to launch a browser on the
  // headless runner.
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: `npm run dev -- --port ${PORT}`,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
})
