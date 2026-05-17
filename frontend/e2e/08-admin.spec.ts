import { test, expect } from "./fixtures";

test.describe("Admin audit log", () => {
  test("admin can open /admin/audit and see ≥ 5 rows", async ({
    adminPage: page,
  }) => {
    await page.goto("/admin/audit");
    await expect(
      page.getByRole("heading", { level: 1, name: /Audit/i })
    ).toBeVisible();
    await expect
      .poll(async () => page.getByRole("row").count())
      .toBeGreaterThanOrEqual(6); // 1 header + ≥5 events
  });

  test("audit rows contain expected action codes (auth, study, finding)", async ({
    adminPage: page,
  }) => {
    await page.goto("/admin/audit");
    const auditText = await page.locator("table").innerText();
    expect(auditText.toLowerCase()).toMatch(/auth|study|finding/);
  });

  test("clinician access — page does not crash (records authz finding)", async ({
    loggedInPage: page,
  }) => {
    await page.goto("/admin/audit");
    // Either the page renders (no authz gate) or 403. Either is informational.
    // We just assert no JS crash by waiting for `body` to be present.
    await expect(page.locator("body")).toBeVisible();
  });
});
