/**
 * Playwright e2e config for the Dars webapp.
 *
 * The webapp talks to a remote backend (no local DB), so the e2e suite runs
 * against a deployed environment rather than spinning up the full stack. Point
 * it at any environment via `E2E_BASE_URL`; it defaults to staging.
 *
 * Tests that need a logged-in user read credentials from the environment
 * (`E2E_EMAIL` / `E2E_PASSWORD`) — never committed. See e2e/README.md.
 *
 * Run:  npm run e2e            (headless)
 *       npm run e2e:headed     (watch the browser)
 *       npm run e2e:ui         (Playwright UI mode)
 */
import { defineConfig, devices } from "@playwright/test";

const BASE_URL =
  process.env.E2E_BASE_URL ?? "https://dars-fe-stage.up.railway.app";

export default defineConfig({
  testDir: "./e2e",
  // One retry absorbs the occasional cold-start / network blip against a
  // remote env without masking a real regression (a real break fails twice).
  retries: process.env.CI ? 2 : 1,
  // Auth flow is inherently serial per worker; keep output readable.
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "list",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
