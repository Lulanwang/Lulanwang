import { test, expect } from "./fixtures";

test.describe("App shell", () => {
  test("sidebar Dashboard link", async ({ loggedInPage: page }) => {
    await page.goto("/worklist");
    await page.getByRole("link", { name: /Dashboard/i }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test("sidebar Worklist link", async ({ loggedInPage: page }) => {
    await page.getByRole("link", { name: /Worklist/i }).click();
    await expect(page).toHaveURL(/\/worklist$/);
  });

  test("sidebar Patients link", async ({ loggedInPage: page }) => {
    await page.getByRole("link", { name: /Patients/i }).click();
    await expect(page).toHaveURL(/\/patients(\/?$|\?)/);
  });

  test("sidebar Analytics link", async ({ loggedInPage: page }) => {
    await page.getByRole("link", { name: /Analytics/i }).click();
    await expect(page).toHaveURL(/\/analytics$/);
  });

  test("sidebar Audit link", async ({ loggedInPage: page }) => {
    await page.getByRole("link", { name: /Audit/i }).click();
    await expect(page).toHaveURL(/\/admin\/audit$/);
  });

  test("theme toggle flips html.dark and persists across reload", async ({
    loggedInPage: page,
  }) => {
    const html = page.locator("html");
    const initialDark = await html.evaluate((el) => el.classList.contains("dark"));
    await page.getByLabel("Toggle theme").click();
    await expect
      .poll(async () => html.evaluate((el) => el.classList.contains("dark")))
      .toBe(!initialDark);
    await page.reload();
    await expect
      .poll(async () => html.evaluate((el) => el.classList.contains("dark")))
      .toBe(!initialDark);
    // Restore for downstream tests
    await page.getByLabel("Toggle theme").click();
  });

  test("Cmd+K opens command palette + Dashboard navigation works", async ({
    loggedInPage: page,
  }) => {
    await page.goto("/worklist");
    await page.keyboard.press("Meta+K");
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await dialog.getByText(/Dashboard/i).first().click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test("Sign out returns to /login", async ({ loggedInPage: page }) => {
    // Open the user menu (avatar button — no accessible name, locate by role)
    const buttons = page.getByRole("button");
    let opened = false;
    const count = await buttons.count();
    for (let i = count - 1; i >= 0; i--) {
      // user-menu avatar is typically rightmost in topbar
      const btn = buttons.nth(i);
      const aria = await btn.getAttribute("aria-haspopup");
      if (aria === "menu") {
        await btn.click();
        opened = true;
        break;
      }
    }
    expect(opened).toBeTruthy();
    await page.getByRole("menuitem", { name: /Sign out/i }).click();
    await expect(page).toHaveURL(/\/login$/);
  });
});
