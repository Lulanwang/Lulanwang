/**
 * Screenshot pass — captures one PNG per page, in both light and dark
 * mode, for inclusion in docs/qa/round11_artifacts/screenshots/.
 *
 * Not part of the assertion suite — runs as its own pseudo-spec. Excluded
 * from the default test run unless explicitly invoked:
 *
 *   npx playwright test e2e/screenshots.spec.ts
 */
import { test } from "./fixtures";
import path from "path";

const OUT = path.resolve(__dirname, "../../docs/qa/round11_artifacts/screenshots");

async function shot(page: any, name: string) {
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: false });
}

test.describe.configure({ mode: "serial" });

test("capture all pages (light)", async ({ loggedInPage: page, studies, multiStudyPseudonym }) => {
  test.setTimeout(120_000);
  await page.goto("/dashboard");
  await page.waitForLoadState("networkidle");
  await shot(page, "01-dashboard-light");

  await page.goto("/worklist");
  await page.waitForLoadState("networkidle");
  await shot(page, "02-worklist-light");

  await page.goto(`/studies/${studies[0].id}`);
  await page.getByLabel("Window / level").waitFor();
  await page.waitForTimeout(2000);
  await shot(page, "03-study-light");

  await page.goto(`/studies/${studies[0].id}/plan`);
  await page.waitForLoadState("networkidle");
  await shot(page, "04-plan-light");

  await page.goto("/patients");
  await page.waitForLoadState("networkidle");
  await shot(page, "05-patients-light");

  if (multiStudyPseudonym) {
    await page.goto(`/patients/${multiStudyPseudonym}`);
    await page.waitForLoadState("networkidle");
    await shot(page, "06-patient-timeline-light");
  }

  await page.goto("/analytics");
  await page.waitForLoadState("networkidle");
  await shot(page, "07-analytics-light");
});

test("capture dashboard + study (dark)", async ({ loggedInPage: page, studies }) => {
  test.setTimeout(60_000);
  await page.goto("/dashboard");
  await page.getByLabel("Toggle theme").click();
  await page.waitForTimeout(500);
  await shot(page, "01-dashboard-dark");

  await page.goto(`/studies/${studies[0].id}`);
  await page.getByLabel("Window / level").waitFor();
  await page.waitForTimeout(2000);
  await shot(page, "03-study-dark");
});
