# Webapp e2e tests

Playwright end-to-end tests that drive a real browser against a **deployed**
environment. The webapp has no local backend/DB, so the suite targets a running
deployment rather than booting the full stack.

## Running

```bash
# headless against staging (default)
E2E_EMAIL=you@org.com E2E_PASSWORD=… npm run e2e

# watch the browser
E2E_EMAIL=… E2E_PASSWORD=… npm run e2e:headed

# Playwright UI mode (pick/replay tests interactively)
E2E_EMAIL=… E2E_PASSWORD=… npm run e2e:ui
```

First time on a machine, install the browser binary once:

```bash
npx playwright install chromium
```

## Configuration

| Env var        | Default                                  | Purpose                                  |
| -------------- | ---------------------------------------- | ---------------------------------------- |
| `E2E_BASE_URL` | `https://dars-fe-stage.up.railway.app`   | Which deployment to test.                |
| `E2E_EMAIL`    | —                                        | Org-admin login on the target env.       |
| `E2E_PASSWORD` | —                                        | Password for `E2E_EMAIL`.                |

Credentials are **never committed** — they come from the environment. Specs that
need a login call `requireCreds()`, which *skips* (not fails) when the vars are
absent, so a fresh checkout stays green until someone wires creds in.

Point at a different env:

```bash
E2E_BASE_URL=http://localhost:3000 E2E_EMAIL=… E2E_PASSWORD=… npm run e2e
```

## What's covered

- **`teacher-app-auth.spec.ts`** — regression for the hard-refresh logout bug:
  after logging in via the dashboard, a full page reload of a teacher-app route
  must keep the user authed and never show the API-key setup prompt.

## Adding a spec

1. Drop a `*.spec.ts` file in `e2e/`.
2. Reuse `e2e/helpers/auth.ts` for login / credential handling.
3. Use `requireCreds()` for any test that needs a logged-in user.
