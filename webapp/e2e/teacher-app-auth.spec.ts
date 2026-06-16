/**
 * Regression: dashboard → teacher app must survive a HARD REFRESH without
 * logging the user out / prompting for an API key.
 *
 * Bug (fixed in webapp/app/teacher-app/layout.tsx): the auth gate reads
 * `useSyncExternalStore`, which returns `false` on the server snapshot AND the
 * first client (hydration) render before flipping to the real localStorage
 * value. The redirect effect fired on that placeholder `false` and bounced an
 * already-authed user to /teacher-app/setup. A soft client-side nav never
 * re-mounts with a server snapshot, so only a HARD REFRESH reproduced it.
 *
 * This spec asserts the user stays in the teacher app after a full reload.
 */
import { expect, test } from "@playwright/test";

import {
  expectNotOnSetup,
  loginViaDashboard,
  readAuthStorage,
  requireCreds,
} from "./helpers/auth";

test.describe("teacher-app auth persistence", () => {
  test("hard refresh keeps the user authed (no API-key prompt)", async ({ page }) => {
    const creds = requireCreds();

    // 1. Log in via the dashboard.
    await loginViaDashboard(page, creds);
    const stored = await readAuthStorage(page);
    expect(stored.session, "login should write an admin session").toBe(true);

    // 2. Walk into the teacher app (soft nav, as a user would from the dashboard).
    await page.goto("/teacher-app/today", { waitUntil: "networkidle" });
    await expectNotOnSetup(page);

    // 3. THE TEST: a full reload (hard refresh) must not bounce to setup.
    await page.reload({ waitUntil: "networkidle" });
    // Give hydration + the useSyncExternalStore re-render time to settle; if the
    // gate is going to wrongly redirect, it does so right after hydration.
    await page.waitForTimeout(2_500);

    await expectNotOnSetup(page);
    await expect(page).toHaveURL(/\/teacher-app\/today/);
    await expect(
      page.getByText(/api key/i),
      "the API-key setup prompt must not appear after a hard refresh",
    ).toHaveCount(0);
  });

  test("direct hard load of a teacher-app URL stays authed", async ({ page }) => {
    const creds = requireCreds();

    // Establish the session, then load a teacher-app route cold (no prior
    // teacher-app nav in this page's history) — the strictest hydration path.
    await loginViaDashboard(page, creds);
    await page.goto("/teacher-app/classes", { waitUntil: "networkidle" });
    await page.waitForTimeout(2_500);

    await expectNotOnSetup(page);
    await expect(page).toHaveURL(/\/teacher-app\/classes/);
  });
});
