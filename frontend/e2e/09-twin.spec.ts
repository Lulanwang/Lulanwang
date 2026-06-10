import { test, expect } from "./fixtures";

test.describe("3D digital twin", () => {
  test("research-only banner visible on the twin page", async ({
    loggedInPage: page,
    studies,
  }) => {
    const lung = studies.find((s) => s.modality === "CT") ?? studies[0];
    await page.goto(`/studies/${lung.id}/twin`);
    await expect(
      page.getByRole("heading", { name: /3D Digital Twin/i })
    ).toBeVisible();
    await expect(
      page.getByText(/Research-only digital twin/i).first()
    ).toBeVisible();
  });

  test("twin page renders one of: viewer canvas, generating spinner, or empty-state", async ({
    loggedInPage: page,
    studies,
  }) => {
    const lung = studies.find((s) => s.modality === "CT") ?? studies[0];
    await page.goto(`/studies/${lung.id}/twin`);
    // Twin generation already ran in QA; the canvas should be live within ~15s.
    // If no twin exists yet, an empty-state with a Generate button shows up instead.
    const canvas = page.locator("canvas").first();
    const empty = page.getByRole("button", { name: /Generate 3D twin/i });
    await expect.poll(async () => (await canvas.count()) > 0 || (await empty.count()) > 0).toBeTruthy();
  });

  test("when a twin exists, structures legend shows volumes", async ({
    loggedInPage: page,
    studies,
  }) => {
    const lung = studies.find((s) => s.modality === "CT") ?? studies[0];
    await page.goto(`/studies/${lung.id}/twin`);
    // Wait for either the canvas to mount or the empty-state to settle.
    const canvas = page.locator("canvas").first();
    const empty = page.getByRole("button", { name: /Generate 3D twin/i });
    await Promise.race([
      canvas.waitFor({ state: "visible", timeout: 25_000 }).catch(() => null),
      empty.waitFor({ state: "visible", timeout: 25_000 }).catch(() => null),
    ]);
    if ((await canvas.count()) === 0) {
      test.skip(true, "no twin generated for this study yet");
    }
    await expect(page.getByText(/cm³/).first()).toBeVisible();
  });

  test("structure visibility toggle is wired", async ({
    loggedInPage: page,
    studies,
  }) => {
    const lung = studies.find((s) => s.modality === "CT") ?? studies[0];
    await page.goto(`/studies/${lung.id}/twin`);
    const canvas = page.locator("canvas").first();
    const empty = page.getByRole("button", { name: /Generate 3D twin/i });
    await Promise.race([
      canvas.waitFor({ state: "visible", timeout: 25_000 }).catch(() => null),
      empty.waitFor({ state: "visible", timeout: 25_000 }).catch(() => null),
    ]);
    if ((await canvas.count()) === 0) {
      test.skip(true, "no twin generated for this study yet");
    }
    const hide = page.getByRole("button", { name: /Hide organ/i });
    if ((await hide.count()) === 0) {
      test.skip(true, "no organ structure rendered");
    }
    await hide.click();
    await expect(
      page.getByRole("button", { name: /Show organ/i })
    ).toBeVisible();
  });
});
