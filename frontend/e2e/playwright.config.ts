import { defineConfig, devices } from "@playwright/test";

/**
 * Round 11 — UI button QA.
 *
 * Server stack is started manually (Postgres + Orthanc + uvicorn + Next dev)
 * because the seed step is not idempotent and we want to control the data
 * cohort, so we do NOT use Playwright's `webServer` block here.
 */
export default defineConfig({
  testDir: "./",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false, // sequential — shared seeded DB rows
  workers: 1,
  retries: 0,
  // Reporter output paths are relative to this config file. We send
  // them up one level so they land in `frontend/test-results/` and
  // `frontend/playwright-report/` — both gitignored.
  reporter: [
    ["list"],
    ["json", { outputFile: "../test-results/results.json" }],
    ["html", { outputFolder: "../playwright-report", open: "never" }],
  ],
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    viewport: { width: 1440, height: 900 },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], channel: undefined },
    },
  ],
});
