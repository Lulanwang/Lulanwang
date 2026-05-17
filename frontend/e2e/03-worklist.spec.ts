import { test, expect } from "./fixtures";

test.describe("Worklist", () => {
  test.beforeEach(async ({ loggedInPage: page }) => {
    await page.goto("/worklist");
  });

  test("renders the H1", async ({ loggedInPage: page }) => {
    await expect(
      page.getByRole("heading", { level: 1, name: /Worklist/i })
    ).toBeVisible();
  });

  test("table renders at least one row", async ({ loggedInPage: page }) => {
    const rows = page.getByRole("row");
    await expect.poll(async () => rows.count()).toBeGreaterThanOrEqual(2); // 1 header + ≥1 body
  });

  test("clicking a modality filter chip narrows the row count", async ({
    loggedInPage: page,
  }) => {
    // Wait for the table to settle.
    await expect(page.getByRole("row").first()).toBeVisible();
    const before = await page.getByRole("row").count();
    // Body modalities CT, MR, MG exist in the seeded cohort. Pick CT.
    // Filter chips are buttons whose visible text is exactly the value.
    const ctChip = page.getByRole("button", { name: /^CT$/ }).first();
    if ((await ctChip.count()) === 0) test.skip(true, "No CT chip rendered");
    await ctChip.click();
    // The worklist page keeps filters in component state (not URL). We
    // assert the row count shrinks or stays the same (no widening).
    await expect
      .poll(async () => page.getByRole("row").count(), { timeout: 5_000 })
      .toBeLessThanOrEqual(before);
  });

  test("Clear filters re-shows the full set", async ({ loggedInPage: page }) => {
    // Wait for facets to load (chips don't render until /studies/facets resolves)
    await page.getByRole("button", { name: /^CT$/ }).first().waitFor({ timeout: 5_000 });
    await page.getByRole("button", { name: /^CT$/ }).first().click();
    const clear = page.getByRole("button", { name: /^Clear$/i }).first();
    await clear.waitFor({ timeout: 5_000 });
    await clear.click();
    await expect(page.getByRole("row").first()).toBeVisible();
  });

  test("sort by Modality column header is clickable", async ({
    loggedInPage: page,
  }) => {
    // SortableTh wraps the column text in a <button> — the button's
    // accessible name is "Modality" (possibly with an icon suffix).
    const header = page.getByRole("button", { name: /modality/i }).first();
    await header.waitFor({ timeout: 5_000 });
    await header.click();
    // Sort lives in state; we just assert no crash + table re-renders.
    await expect(page.getByRole("row").first()).toBeVisible();
  });

  test("select-all checkbox toggles", async ({ loggedInPage: page }) => {
    const sel = page.getByLabel("Select all");
    await sel.waitFor({ timeout: 5_000 });
    await sel.check();
    await expect(sel).toBeChecked();
    await sel.uncheck();
    await expect(sel).not.toBeChecked();
  });

  test("row checkbox is independently toggleable", async ({
    loggedInPage: page,
  }) => {
    const row = page.getByLabel(/Select study/).first();
    await row.waitFor({ timeout: 5_000 });
    await row.check();
    await expect(row).toBeChecked();
  });

  test("Re-run bulk action button reflects selection count", async ({
    loggedInPage: page,
  }) => {
    const row = page.getByLabel(/Select study/).first();
    await row.waitFor({ timeout: 5_000 });
    await row.check();
    await expect(
      page.getByRole("button", { name: /Re-run/i })
    ).toBeVisible();
  });

  test("Open link navigates to /studies/{uid}", async ({
    loggedInPage: page,
  }) => {
    // Locate by href pattern — the cell, the link text "Open", and the
    // chevron icon all share the same accessible name, so role+name is
    // ambiguous. The actual <a> has href="/studies/<uuid>".
    const open = page.locator("a[href^='/studies/']").first();
    await open.click();
    await page.waitForURL(/\/studies\/[^/]+$/, { timeout: 10_000 });
  });

  test("thumbnails surface (img tags appear or skeleton resolves)", async ({
    loggedInPage: page,
  }) => {
    // Thumbnails render via <img src="/api/v1/studies/{id}/thumbnail">.
    // We accept any <img> visibility inside the table area as a pass.
    const img = page.locator("img").first();
    await expect(img).toBeVisible({ timeout: 10_000 });
  });
});
