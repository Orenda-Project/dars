/**
 * Shared auth helpers for e2e specs.
 *
 * Credentials come from the environment so nothing secret is committed:
 *   E2E_EMAIL, E2E_PASSWORD  — a real org-admin login on the target env.
 * `requireCreds()` skips the test (rather than failing) when they're absent,
 * so the suite stays green on a checkout that hasn't configured them.
 */
import { expect, type Page, test } from "@playwright/test";

export interface Creds {
  email: string;
  password: string;
}

/** Pull credentials from env, or skip the calling test if they're missing. */
export function requireCreds(): Creds {
  const email = process.env.E2E_EMAIL;
  const password = process.env.E2E_PASSWORD;
  test.skip(
    !email || !password,
    "Set E2E_EMAIL and E2E_PASSWORD to run authenticated e2e specs.",
  );
  return { email: email!, password: password! };
}

/**
 * Log in through the dashboard login form and wait for the overview page.
 * Mirrors a real user: this is also what writes `dars_admin_session` (and,
 * best-effort, `dars_org_api_key`) into localStorage.
 */
export async function loginViaDashboard(page: Page, creds: Creds): Promise<void> {
  await page.goto("/dashboard/login", { waitUntil: "networkidle" });
  await page.fill("input[type=email]", creds.email);
  await page.fill("input[type=password]", creds.password);
  await page.click("button[type=submit]");
  await page.waitForURL("**/dashboard/overview", { timeout: 30_000 });
}

/** Read the two auth credentials out of localStorage. */
export async function readAuthStorage(
  page: Page,
): Promise<{ session: boolean; apiKey: boolean }> {
  return page.evaluate(() => ({
    session: !!localStorage.getItem("dars_admin_session"),
    apiKey: !!localStorage.getItem("dars_org_api_key"),
  }));
}

/** Assert the page is NOT showing the teacher-app API-key setup prompt. */
export async function expectNotOnSetup(page: Page): Promise<void> {
  expect(page.url(), "should not be bounced to the API-key setup page").not.toContain(
    "/teacher-app/setup",
  );
}
