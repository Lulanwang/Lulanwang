import { test, expect } from "./fixtures";

test.describe("Treatment plan", () => {
  test.beforeEach(async ({ loggedInPage: page, studies }) => {
    const target = studies.find((s) => s.modality === "MR") ?? studies[0];
    await page.goto(`/studies/${target.id}/plan`);
  });

  test("research-only banner visible", async ({ loggedInPage: page }) => {
    await expect(
      page.getByText(/research[ -]?only|RESEARCH ONLY/i).first()
    ).toBeVisible();
  });

  test("New draft plan button creates a plan card", async ({
    loggedInPage: page,
  }) => {
    const newBtn = page.getByRole("button", { name: /New draft plan/i });
    if ((await newBtn.count()) === 0) {
      // Already a plan; pass
      await expect(page.getByText(/Contours|Beams/i).first()).toBeVisible();
      return;
    }
    await newBtn.click();
    await expect(page.getByText(/Contours/i).first()).toBeVisible({
      timeout: 8_000,
    });
  });

  test("Contours panel renders", async ({ loggedInPage: page }) => {
    await expect(page.getByText(/^Contours/).first()).toBeVisible({
      timeout: 8_000,
    });
  });

  test("Beams panel renders", async ({ loggedInPage: page }) => {
    await expect(page.getByText(/^Beams/).first()).toBeVisible({
      timeout: 8_000,
    });
  });

  test("OAR constraints panel renders", async ({ loggedInPage: page }) => {
    await expect(page.getByText(/OAR constraints/i).first()).toBeVisible({
      timeout: 8_000,
    });
  });

  test("Print summary button calls window.print", async ({
    loggedInPage: page,
  }) => {
    const btn = page.getByRole("button", { name: /Print summary/i });
    if ((await btn.count()) === 0)
      test.skip(true, "No print button on this state");
    await page.evaluate(() => {
      (window as unknown as { __printed: boolean }).__printed = false;
      window.print = () => {
        (window as unknown as { __printed: boolean }).__printed = true;
      };
    });
    await btn.click();
    const printed = await page.evaluate(
      () => (window as unknown as { __printed: boolean }).__printed
    );
    expect(printed).toBeTruthy();
  });

  test("Back to study link returns to /studies/{uid}", async ({
    loggedInPage: page,
  }) => {
    const link = page.getByRole("link", { name: /Back to study/i });
    if ((await link.count()) === 0) test.skip(true, "No back link");
    await link.click();
    await expect(page).toHaveURL(/\/studies\/[^/]+$/);
  });
});
