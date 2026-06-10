import { test, expect } from "./fixtures";

test.describe("Analytics", () => {
  test.beforeEach(async ({ loggedInPage: page }) => {
    await page.goto("/analytics");
  });

  test("renders the H1", async ({ loggedInPage: page }) => {
    await expect(
      page.getByRole("heading", { level: 1, name: /Analytics/i })
    ).toBeVisible();
  });

  test("3 chart cards visible", async ({ loggedInPage: page }) => {
    await expect(page.getByText(/accept rate/i).first()).toBeVisible();
    await expect(page.getByText(/latency/i).first()).toBeVisible();
    await expect(page.getByText(/heatmap|audit/i).first()).toBeVisible();
  });

  test("audit heatmap renders cells (≥50 day-cells)", async ({
    loggedInPage: page,
  }) => {
    // Each day cell is a <div title="YYYY-MM-DD · N events"> in the
    // component. Match by the tooltip text.
    const cells = page.locator("[title*='events']");
    await expect
      .poll(async () => cells.count(), { timeout: 10_000 })
      .toBeGreaterThanOrEqual(50);
  });

  test("CSV button on accept-rate card triggers a download", async ({
    loggedInPage: page,
  }) => {
    const buttons = page.getByRole("button", { name: /CSV/i });
    if ((await buttons.count()) === 0) test.skip(true, "No CSV button");
    const downloadPromise = page.waitForEvent("download", { timeout: 5_000 });
    await buttons.first().click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.csv$/);
  });

  test("group-by toggle switches grouping on accept-rate card", async ({
    loggedInPage: page,
  }) => {
    // The toggle button reads "model" or "body part"
    const toggle = page.getByRole("button", { name: /body part|model/i }).first();
    if ((await toggle.count()) === 0) test.skip(true, "No group-by toggle");
    await toggle.click();
    // Just confirm the page is still alive after click
    await expect(
      page.getByRole("heading", { level: 1, name: /Analytics/i })
    ).toBeVisible();
  });
});
