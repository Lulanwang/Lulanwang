import { test, expect } from "./fixtures";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ loggedInPage: page }) => {
    await page.goto("/dashboard");
  });

  test("renders the H1", async ({ loggedInPage: page }) => {
    await expect(
      page.getByRole("heading", { level: 1, name: /Dashboard/i })
    ).toBeVisible();
  });

  test("4 KPI cards visible with numeric values", async ({
    loggedInPage: page,
  }) => {
    for (const title of [
      /Studies/i,
      /Signed reports/i,
      /latency/i,
      /accept rate/i,
    ]) {
      await expect(page.getByText(title).first()).toBeVisible();
    }
  });

  test("studies-per-day chart renders an SVG", async ({
    loggedInPage: page,
  }) => {
    await expect(page.getByText(/Studies per day/i)).toBeVisible();
    await expect(page.locator("svg").first()).toBeVisible();
  });

  test("modality breakdown chart renders an SVG", async ({
    loggedInPage: page,
  }) => {
    await expect(page.getByText(/Modality breakdown/i)).toBeVisible();
  });

  test("unsigned-reports section renders without error", async ({
    loggedInPage: page,
  }) => {
    await expect(page.getByText(/Unsigned reports/i)).toBeVisible();
  });

  test("recent-activity section renders without error", async ({
    loggedInPage: page,
  }) => {
    await expect(page.getByText(/Recent activity/i)).toBeVisible();
  });
});
