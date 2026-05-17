import { test, expect } from "./fixtures";

test.describe("Login", () => {
  test("renders the form with the seeded clinician email pre-filled", async ({
    page,
  }) => {
    await page.goto("/login");
    const email = page.getByLabel(/email/i);
    await expect(email).toHaveValue("clinician@lulan.local");
    await expect(page.getByRole("button", { name: /sign in/i })).toBeEnabled();
  });

  test("valid credentials → /dashboard", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email/i).fill("clinician@lulan.local");
    await page.getByLabel(/password/i).fill("clinician_demo_password");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test("wrong password keeps user on /login (no redirect to /dashboard)", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.getByLabel(/email/i).fill("clinician@lulan.local");
    await page.getByLabel(/password/i).fill("wrong-password");
    await page.getByRole("button", { name: /sign in/i }).click();
    // The api helper redirects 401s back to /login itself; we just
    // verify the user did NOT land on /dashboard.
    await page.waitForTimeout(1_000);
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
  });
});
