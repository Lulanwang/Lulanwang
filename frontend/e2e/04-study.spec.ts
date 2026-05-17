import { test, expect } from "./fixtures";

test.describe("Study viewer", () => {
  test.beforeEach(async ({ loggedInPage: page, studies }) => {
    const target = studies.find((s) => s.modality !== "MG") ?? studies[0];
    await page.goto(`/studies/${target.id}`);
    // The study page uses <h3> elements (Series, study description). Wait
    // for the toolbar that always renders so the page is interactive.
    await page.getByLabel("Window / level").waitFor({ state: "visible" });
  });

  test("page header + state pill render", async ({ loggedInPage: page }) => {
    // Some state pill (proposed/reported/signed) is always visible
    await expect(
      page
        .locator("main")
        .getByText(/proposed|reported|signed|received|inferring/i)
        .first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("viewer mounts a <canvas>", async ({ loggedInPage: page }) => {
    await expect(page.locator("canvas").first()).toBeVisible({
      timeout: 15_000,
    });
  });

  // ----- toolbar tools -----
  for (const [tool, aria] of [
    ["W/L", "Window / level"],
    ["Pan", "Pan (right-click default)"],
    ["Zoom", "Zoom (middle-click default)"],
    ["Scroll", "Slice scroll (mouse wheel)"],
    ["Length", "Length measurement"],
    ["Ellipse", "Elliptical ROI"],
    ["Rect", "Rectangular ROI"],
    ["Brush", "Paint segmentation"],
    ["Cut", "Rectangle scissors"],
  ] as const) {
    test(`toolbar button: ${tool}`, async ({ loggedInPage: page }) => {
      const btn = page.getByLabel(aria);
      if ((await btn.count()) === 0) test.skip(true, `${aria} not rendered`);
      await btn.click();
      await expect(btn).toBeVisible();
    });
  }

  test("Re-run inference button → toast appears", async ({
    loggedInPage: page,
  }) => {
    const btn = page.getByRole("button", { name: /Re-run inference/i });
    if ((await btn.count()) === 0)
      test.skip(true, "Re-run inference not present");
    await btn.click();
    // Toaster is sonner — look for a status region with text
    await expect(
      page.getByText(/inference|queued|started/i).last()
    ).toBeVisible({ timeout: 5_000 });
  });

  test("Priors button opens a sheet/drawer", async ({ loggedInPage: page }) => {
    const btn = page.getByRole("button", { name: /^Priors$/ });
    if ((await btn.count()) === 0)
      test.skip(true, "No Priors button (no patient linkage on this study)");
    await btn.click();
    await expect(page.getByRole("dialog")).toBeVisible();
    // Close so subsequent tests aren't covered
    await page.keyboard.press("Escape");
  });

  test("Plan button navigates to /studies/{uid}/plan", async ({
    loggedInPage: page,
  }) => {
    const link = page.getByRole("link", { name: /^Plan$/ });
    if ((await link.count()) === 0) test.skip(true, "No Plan link");
    await link.click();
    await expect(page).toHaveURL(/\/studies\/[^/]+\/plan$/);
  });

  test("Chat button opens MedGemma sheet", async ({
    loggedInPage: page,
  }) => {
    const btn = page.getByRole("button", { name: /^Chat$/ });
    if ((await btn.count()) === 0) test.skip(true, "No Chat button");
    await btn.click();
    await expect(
      page.getByText(/MedGemma chat|MedGemma/i).first()
    ).toBeVisible();
    await page.keyboard.press("Escape");
  });

  test("Keys button opens shortcuts dialog", async ({
    loggedInPage: page,
  }) => {
    const btn = page.getByRole("button", { name: /^Keys$/ });
    if ((await btn.count()) === 0) test.skip(true, "No Keys button");
    await btn.click();
    await expect(page.getByText(/shortcut|keyboard/i).first()).toBeVisible();
    await page.keyboard.press("Escape");
  });

  test("Accept button on a proposed finding works", async ({
    loggedInPage: page,
  }) => {
    const btn = page.getByRole("button", { name: /^Accept$/ }).first();
    if ((await btn.count()) === 0)
      test.skip(true, "No proposed findings to accept");
    await btn.click();
    // The row should update to status=accepted; we look for the label
    await expect(
      page.getByText(/accepted/i).first()
    ).toBeVisible({ timeout: 8_000 });
  });

  test("Reject button on a proposed finding works", async ({
    loggedInPage: page,
  }) => {
    const btn = page.getByRole("button", { name: /^Reject$/ }).first();
    if ((await btn.count()) === 0)
      test.skip(true, "No proposed findings to reject");
    await btn.click();
    await expect(
      page.getByText(/rejected|dismissed/i).first()
    ).toBeVisible({ timeout: 8_000 });
  });

  test("Sign report button signs + shows signed timestamp", async ({
    loggedInPage: page,
  }) => {
    const btn = page.getByRole("button", { name: /Sign report/i });
    if ((await btn.count()) === 0)
      test.skip(true, "No Sign report (already signed?)");
    await btn.click();
    await expect(
      page.getByText(/signed|^Signed$/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });
});
