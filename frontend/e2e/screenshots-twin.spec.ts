/**
 * Round 12 — capture screenshots of the 3D digital twin viewer
 * across the three seeded modalities. Each capture waits for the
 * canvas + GLB load + Bounds auto-fit before snapping.
 *
 * Runs outside the default test suite:
 *   npx playwright test e2e/screenshots-twin.spec.ts
 */
import path from "path";
import { test } from "./fixtures";

const OUT = path.resolve(
  __dirname,
  "../../docs/qa/round12_artifacts/screenshots"
);

async function shot(page: import("@playwright/test").Page, name: string) {
  await page.screenshot({
    path: path.join(OUT, `${name}.png`),
    fullPage: false,
  });
}

test.describe.configure({ mode: "serial" });

test("capture twin viewer per modality", async ({
  loggedInPage: page,
  studies,
}) => {
  test.setTimeout(120_000);
  const samples = [
    { modality: "CT", name: "twin-lung-ct" },
    { modality: "MR", name: "twin-brain-mr" },
    { modality: "MG", name: "twin-breast-mg" },
  ];
  for (const { modality, name } of samples) {
    const study = studies.find((s) => s.modality === modality);
    if (!study) continue;
    await page.goto(`/studies/${study.id}/twin`);
    const canvas = page.locator("canvas").first();
    const empty = page.getByRole("button", { name: /Generate 3D twin/i });
    await Promise.race([
      canvas.waitFor({ state: "visible", timeout: 25_000 }).catch(() => null),
      empty.waitFor({ state: "visible", timeout: 25_000 }).catch(() => null),
    ]);
    // Give Bounds + Orbit a tick to finish framing.
    await page.waitForTimeout(1500);
    await shot(page, name);
  }
});
