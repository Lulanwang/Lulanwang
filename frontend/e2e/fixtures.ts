import { test as base, expect, type Page } from "@playwright/test";

export type SeededStudy = {
  id: string;
  modality: string;
  body_part: string;
  study_instance_uid: string;
};

type Fixtures = {
  loggedInPage: Page;
  adminPage: Page;
  /** All seeded studies, fetched once per worker. */
  studies: SeededStudy[];
  /** A patient pseudonym with ≥ 2 studies, for change-report tests. */
  multiStudyPseudonym: string;
};

const API = process.env.LULAN_API_BASE ?? "http://localhost:8000/api/v1";

async function loginViaUI(page: Page, email: string, password: string) {
  await page.goto("/login");
  // The login form re-uses the seeded clinician account, so the email
  // field is often pre-populated. Always overwrite to be deterministic.
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL("**/dashboard", { timeout: 15_000 });
}

async function fetchStudies(token: string): Promise<SeededStudy[]> {
  const r = await fetch(`${API}/studies/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error(`fetch studies: ${r.status}`);
  return (await r.json()) as SeededStudy[];
}

async function backendToken(email: string, password: string): Promise<string> {
  const r = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error(`auth: ${r.status}`);
  const body = (await r.json()) as { token: string };
  return body.token;
}

export const test = base.extend<Fixtures>({
  loggedInPage: async ({ page }, use) => {
    await loginViaUI(page, "clinician@lulan.local", "clinician_demo_password");
    await use(page);
  },

  adminPage: async ({ page }, use) => {
    await loginViaUI(page, "admin@lulan.local", "admin_demo_password");
    await use(page);
  },

  studies: async ({}, use) => {
    const token = await backendToken(
      "clinician@lulan.local",
      "clinician_demo_password"
    );
    const list = await fetchStudies(token);
    if (!list.length) throw new Error("no seeded studies — run qa.seed_qa first");
    await use(list);
  },

  multiStudyPseudonym: async ({}, use) => {
    const token = await backendToken(
      "clinician@lulan.local",
      "clinician_demo_password"
    );
    const r = await fetch(`${API}/patients/`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const patients = (await r.json()) as Array<{
      pseudonym: string;
      study_count: number;
    }>;
    const multi = patients.find((p) => p.study_count >= 2);
    await use(multi?.pseudonym ?? "");
  },
});

export { expect };
