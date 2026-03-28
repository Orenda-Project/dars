# Dars SDK Design — `@dars/node` + `@dars/react`

**Date:** 2026-03-28
**Status:** Approved

---

## Goal

Make it as easy as possible for FDS teams to integrate Dars LP generation into their own apps — with maximum DX for both human developers and AI agents (Claude, Cursor, etc.).

Users have minimal Dars knowledge. The SDK must hand-hold: clear types, descriptive errors, JSDoc on everything, one obvious way to do each thing.

---

## Packages

Two independent npm packages under the `@dars/` scope:

| Package | Who uses it | Lives in |
|---|---|---|
| `@dars/node` | FDS backend servers | `packages/dars-node/` |
| `@dars/react` | FDS React frontends | `packages/dars-react/` |

They are independent — teams can use either or both.

---

## `@dars/node`

### Responsibilities
- `DarsClient` class — instantiated with secret key + base URL
- `lessonPlans.create(params)` — `POST /api/v1/lesson-plans`
- `lessonPlans.list(options)` — `GET /api/v1/lesson-plans`
- `lessonPlans.get(id)` — `GET /api/v1/lesson-plans/{id}`
- `createDarsHandler()` — middleware for Next.js / Express that proxies browser requests to Dars, keeping the secret key server-side
- Full TypeScript types for all inputs and outputs
- Typed error classes

### Usage — backend only

```ts
import Dars from '@dars/node'

const dars = new Dars({ apiKey: process.env.DARS_SECRET_KEY })

const lp = await dars.lessonPlans.create({
  grade: '3',
  subject: 'Maths',
  page_number: '10',
  curriculum: 'ICT',
})
```

### Usage — middleware (Next.js)

```ts
// app/api/dars/[...path]/route.ts
import { createDarsHandler } from '@dars/node/middleware'

export const { GET, POST } = createDarsHandler({
  apiKey: process.env.DARS_SECRET_KEY,
  baseUrl: process.env.DARS_BASE_URL, // defaults to https://api.dars.taleemabad.com
})
```

### Package structure

```
packages/dars-node/
  src/
    client.ts         — DarsClient class
    lesson-plans.ts   — lessonPlans resource methods
    middleware.ts     — createDarsHandler
    errors.ts         — typed error classes
    types.ts          — LessonPlan, CreateLessonPlanParams, etc.
    index.ts          — public exports
  package.json
  tsconfig.json
```

### Dependencies
- Zero runtime dependencies — uses native `fetch`
- TypeScript dev dependency only

---

## `@dars/react`

### Responsibilities
- `<DarsProvider endpoint="/api/dars">` — sets proxy URL, no API key in browser
- `useLessonPlan()` hook — `{ generate, lessonPlan, isLoading, error }`
- `useLessonPlans(options?)` hook — `{ lessonPlans, total, isLoading, error }` — options: `{ limit?, offset? }`
- `<LessonPlanGenerator>` — pre-built form with `classNames` API for styling
- `<LessonPlanViewer html={...}>` — safe HTML renderer (sanitized, no XSS)
- No dependency on `@dars/node` — types are inlined

### Usage — hook (full control)

```tsx
import { useLessonPlan, LessonPlanViewer } from '@dars/react'

export default function Page() {
  const { generate, lessonPlan, isLoading, error } = useLessonPlan()

  return (
    <>
      <button onClick={() => generate({ grade: '3', subject: 'Maths', page_number: '10', curriculum: 'ICT' })}>
        {isLoading ? 'Generating... (~60s)' : 'Generate LP'}
      </button>
      {error && <p>{error.message}</p>}
      {lessonPlan && <LessonPlanViewer html={lessonPlan.content} />}
    </>
  )
}
```

### Usage — pre-built component (minimum code)

```tsx
import { LessonPlanGenerator } from '@dars/react'

export default function Page() {
  return (
    <LessonPlanGenerator
      onSuccess={(lp) => console.log(lp.id)}
      classNames={{ button: 'my-btn', error: 'my-error' }}
    />
  )
}
```

### Package structure

```
packages/dars-react/
  src/
    provider.tsx
    hooks/
      use-lesson-plan.ts
      use-lesson-plans.ts
    components/
      lesson-plan-generator.tsx
      lesson-plan-viewer.tsx
    types.ts
    index.ts
  package.json
  tsconfig.json
```

### Dependencies
- Peer dependency: `react >= 18`
- Zero other runtime dependencies

---

## Security Model

- `sk_xxx` — secret key. Server-side only. Used by `@dars/node`.
- The React SDK talks to the FDS team's own backend proxy (`/api/dars`), never directly to Dars. The secret key never reaches the browser.

---

## Error Handling

Typed error classes — every failure is catchable by type:

```ts
import { DarsAuthError, DarsValidationError, DarsNotFoundError, DarsApiError } from '@dars/node'

try {
  await dars.lessonPlans.create(...)
} catch (e) {
  if (e instanceof DarsAuthError)       // bad API key
  if (e instanceof DarsValidationError) // bad params, e.message names the field
  if (e instanceof DarsNotFoundError)   // LP doesn't exist
  if (e instanceof DarsApiError)        // unexpected server error, includes status code
}
```

Descriptive messages:
```
DarsValidationError: 'grade' is required
DarsValidationError: 'curriculum' must be one of: ICT, Punjab
DarsAuthError: Invalid API key. Get your key from the Dars admin panel.
```

React hook `error` is typed — not `unknown`.

---

## DX Principles

These apply to every public API in both packages:

- **Full TypeScript types** — AI agents and IDEs autocomplete correctly without reading docs
- **JSDoc on every public method** — visible in editor tooltips and AI context windows
- **Descriptive error messages** — specific enough to self-correct without reading docs
- **One obvious way to do each thing** — no ambiguous overloads or multiple patterns for the same operation
- **60s wait is communicated** — loading states and messages make the wait expected, not surprising

---

## Build & Publishing

- pnpm workspace (already in use)
- `tsup` for bundling — ESM + CJS output
- Published to npm under `@dars/` scope
- Versioned independently

---

## Testing Strategy

**`@dars/node`** (vitest):
- Mock `fetch` — no real server needed
- Each method: happy path + each error type + network failure
- Middleware: correct headers proxied, secret key never forwarded

**`@dars/react`** (vitest + @testing-library/react):
- Mock fetch calls directly
- Hook state transitions: idle → loading → success / error
- `LessonPlanViewer` sanitizes HTML (XSS check)
- `LessonPlanGenerator` form validates before firing request

Not tested: end-to-end against real Dars API (server's responsibility), visual appearance.

---

## Out of Scope

- Vue / Angular / Svelte adapters
- React Native
- Python or other language SDKs
- Publishable key / two-key system (revisit when public-facing embed is needed)
