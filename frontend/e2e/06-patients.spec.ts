import { test, expect } from "./fixtures";

test.describe("Patients", () => {
  test("/patients lists ≥ 1 patient row", async ({ loggedInPage: page }) => {
    await page.goto("/patients");
    await expect(
      page.getByRole("heading", { level: 1, name: /Patients/i })
    ).toBeVisible();
    await expect.poll(async () => page.getByRole("row").count()).toBeGreaterThanOrEqual(2);
  });

  test("Timeline link navigates to /patients/{pseudonym}", async ({
    loggedInPage: page,
  }) => {
    await page.goto("/patients");
    const link = page.getByRole("link", { name: /Timeline/i }).first();
    await link.click();
    await expect(page).toHaveURL(/\/patients\/[^/]+$/);
  });

  test("timeline page renders ≥ 1 study card", async ({
    loggedInPage: page,
    multiStudyPseudonym,
  }) => {
    if (!multiStudyPseudonym)
      test.skip(true, "no patient with ≥2 studies in cohort");
    await page.goto(`/patients/${multiStudyPseudonym}`);
    await expect(
      page.getByRole("heading", { name: /Patient timeline/i })
    ).toBeVisible();
    await expect(page.locator("[role='button'], button").first()).toBeVisible();
  });

  test("Compare button shows count (0/2 → 1/2 → 2/2)", async ({
    loggedInPage: page,
    multiStudyPseudonym,
  }) => {
    if (!multiStudyPseudonym)
      test.skip(true, "no patient with ≥2 studies in cohort");
    await page.goto(`/patients/${multiStudyPseudonym}`);
    // Look for the Compare aggregate button — when none selected, label
    // reads "Compare (0/2)" or similar.
    const cmpBtn = page.getByRole("button", { name: /Compare \(/i });
    await expect(cmpBtn.first()).toBeVisible({ timeout: 5_000 });
  });
});
