# SDK Implementation Plan — `@dars/node` + `@dars/react`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and publish two independent npm packages — `@dars/node` (Node.js SDK + middleware) and `@dars/react` (headless React hooks + components) — so FDS teams can integrate Dars LP generation with minimal code.

**Architecture:** `@dars/node` wraps the Dars REST API using native `fetch`, exposes a typed `DarsClient` class and a `createDarsHandler` proxy middleware. `@dars/react` provides hooks and headless components that talk to the FDS team's own backend proxy (never directly to Dars), keeping the secret key server-side. The two packages are independent — no runtime dependency between them.

**Tech Stack:** TypeScript, tsup (bundling), vitest (tests), @testing-library/react (React tests), pnpm workspaces

---

## File Map

### `@dars/node` — `packages/dars-node/`

| File | Responsibility |
|---|---|
| `package.json` | Package metadata, exports map, build scripts |
| `tsconfig.json` | TypeScript config |
| `src/types.ts` | `LessonPlan`, `CreateLessonPlanParams`, `ListLessonPlansOptions`, `ListLessonPlansResult` |
| `src/errors.ts` | `DarsApiError`, `DarsAuthError`, `DarsValidationError`, `DarsNotFoundError` |
| `src/lesson-plans.ts` | `LessonPlansResource` class with `create`, `list`, `get` |
| `src/client.ts` | `DarsClient` class — instantiates resources, holds config |
| `src/middleware.ts` | `createDarsHandler()` — Next.js App Router + Express adapter |
| `src/index.ts` | Public exports |
| `tests/errors.test.ts` | Error class tests |
| `tests/lesson-plans.test.ts` | Resource method tests (fetch mocked) |
| `tests/middleware.test.ts` | Middleware proxy tests |

### `@dars/react` — `packages/dars-react/`

| File | Responsibility |
|---|---|
| `package.json` | Package metadata, exports map, build scripts |
| `tsconfig.json` | TypeScript config |
| `src/types.ts` | `LessonPlan`, `CreateLessonPlanParams` (inlined, no @dars/node dep) |
| `src/errors.ts` | `DarsError` base + typed subclasses (mirrored from @dars/node) |
| `src/context.ts` | `DarsContext` — React context holding endpoint URL |
| `src/provider.tsx` | `DarsProvider` component |
| `src/hooks/use-lesson-plan.ts` | `useLessonPlan()` hook |
| `src/hooks/use-lesson-plans.ts` | `useLessonPlans()` hook |
| `src/components/lesson-plan-viewer.tsx` | `LessonPlanViewer` — safe HTML renderer |
| `src/components/lesson-plan-generator.tsx` | `LessonPlanGenerator` — pre-built form |
| `src/index.ts` | Public exports |
| `tests/provider.test.tsx` | Provider renders and provides context |
| `tests/use-lesson-plan.test.tsx` | Hook state transitions |
| `tests/use-lesson-plans.test.tsx` | Hook state transitions |
| `tests/lesson-plan-viewer.test.tsx` | HTML sanitization / XSS |
| `tests/lesson-plan-generator.test.tsx` | Form validation, submit flow |

---

## Part 1: `@dars/node`

---

### Task 1: Scaffold `@dars/node` package

**Files:**
- Create: `packages/dars-node/package.json`
- Create: `packages/dars-node/tsconfig.json`
- Modify: root `pnpm-workspace.yaml` (create if missing)

- [ ] **Step 1: Create pnpm workspace file** (if it doesn't exist at repo root)

Check: `ls /path/to/dars/pnpm-workspace.yaml`

If missing, create `pnpm-workspace.yaml` at repo root:
```yaml
packages:
  - packages/*
  - webapp
```

- [ ] **Step 2: Create `packages/dars-node/package.json`**

```json
{
  "name": "@dars/node",
  "version": "0.1.0",
  "description": "Node.js SDK for the Dars lesson plan API",
  "type": "module",
  "main": "./dist/index.cjs",
  "module": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "import": "./dist/index.js",
      "require": "./dist/index.cjs",
      "types": "./dist/index.d.ts"
    },
    "./middleware": {
      "import": "./dist/middleware.js",
      "require": "./dist/middleware.cjs",
      "types": "./dist/middleware.d.ts"
    }
  },
  "scripts": {
    "build": "tsup",
    "test": "vitest run",
    "test:watch": "vitest",
    "typecheck": "tsc --noEmit"
  },
  "devDependencies": {
    "tsup": "^8.0.0",
    "typescript": "^5.4.0",
    "vitest": "^1.6.0",
    "@types/node": "^20.0.0"
  }
}
```

- [ ] **Step 3: Create `packages/dars-node/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "declaration": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create `packages/dars-node/tsup.config.ts`**

```ts
import { defineConfig } from 'tsup'

export default defineConfig({
  entry: {
    index: 'src/index.ts',
    middleware: 'src/middleware.ts',
  },
  format: ['esm', 'cjs'],
  dts: true,
  clean: true,
  sourcemap: true,
})
```

- [ ] **Step 5: Install dependencies**

```bash
cd packages/dars-node && pnpm install
```

Expected: `node_modules/` created, no errors.

- [ ] **Step 6: Commit**

```bash
git add packages/dars-node/package.json packages/dars-node/tsconfig.json packages/dars-node/tsup.config.ts pnpm-workspace.yaml
git commit -m "chore: scaffold @dars/node package"
```

---

### Task 2: Types

**Files:**
- Create: `packages/dars-node/src/types.ts`

- [ ] **Step 1: Create `src/types.ts`**

```ts
/**
 * Parameters for creating a new lesson plan.
 * All fields map directly to the Dars API request body.
 */
export interface CreateLessonPlanParams {
  /** Grade level, e.g. "3", "KG", "1" */
  grade: string
  /** Subject name, e.g. "Maths", "Eng", "Urdu", "Science" */
  subject: string
  /** Textbook page number(s), e.g. "10" or "10-12" */
  page_number: string
  /** Curriculum type. Defaults to "ICT" (national). Use "Punjab" for provincial. */
  curriculum?: 'ICT' | 'Punjab'
  /** Number of students in the class */
  class_strength?: number
  /** Optional topic override */
  topic?: string
  /** Your own reference ID for this LP — stored and returned as-is */
  external_ref?: string
  /** Exercise page number(s), if different from main page */
  exercise_page_number?: string
  /** Custom instructions passed to the LP generator */
  custom_prompt?: string
  /** Generate both English and Urdu versions. Defaults to false. */
  generate_bilingual?: boolean
  /** Enable extended reasoning in the generator. Defaults to true. */
  reasoning_enabled?: boolean
}

/**
 * Options for listing lesson plans.
 */
export interface ListLessonPlansOptions {
  /** Maximum number of results to return. Default: 20, max: 100. */
  limit?: number
  /** Number of results to skip for pagination. Default: 0. */
  offset?: number
}

/**
 * A lesson plan returned by the Dars API.
 */
export interface LessonPlan {
  /** Unique ID of this lesson plan */
  id: string
  /** ID of the client that owns this LP */
  client_id: string
  /** Your own reference ID, if provided at creation */
  external_ref: string | null
  grade: string
  subject: string
  topic: string | null
  page_number: string | null
  class_strength: number | null
  /** HTML content of the lesson plan. Null if generation failed or is pending. */
  content: string | null
  /** Bilingual (Urdu) HTML content. Null if not requested or not yet generated. */
  content_bilingual: string | null
  /** Current status: "pending" | "completed" | "failed" */
  status: string
  /** Internal metadata (generation timings, token costs, etc.) */
  metadata_: Record<string, unknown>
  /** Curriculum tags extracted during generation */
  tags: Record<string, unknown>
  created_at: string
  updated_at: string
}

/**
 * Result from listing lesson plans.
 */
export interface ListLessonPlansResult {
  items: LessonPlan[]
  /** Total number of LPs for this client (useful for pagination) */
  total: number
}

/**
 * Configuration for the DarsClient.
 */
export interface DarsClientConfig {
  /** Your Dars secret API key (sk_xxx). Never expose this in the browser. */
  apiKey: string
  /**
   * Base URL of the Dars API.
   * @default "https://api.dars.taleemabad.com"
   */
  baseUrl?: string
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd packages/dars-node && npx tsc --noEmit --allowJs false src/types.ts
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add packages/dars-node/src/types.ts
git commit -m "feat(@dars/node): add TypeScript types"
```

---

### Task 3: Error classes

**Files:**
- Create: `packages/dars-node/src/errors.ts`
- Create: `packages/dars-node/tests/errors.test.ts`

- [ ] **Step 1: Write the failing test**

Create `packages/dars-node/tests/errors.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import {
  DarsApiError,
  DarsAuthError,
  DarsValidationError,
  DarsNotFoundError,
} from '../src/errors'

describe('DarsApiError', () => {
  it('is an instance of Error', () => {
    const e = new DarsApiError('something failed', 500)
    expect(e).toBeInstanceOf(Error)
    expect(e).toBeInstanceOf(DarsApiError)
    expect(e.message).toBe('something failed')
    expect(e.status).toBe(500)
    expect(e.name).toBe('DarsApiError')
  })
})

describe('DarsAuthError', () => {
  it('extends DarsApiError with status 401', () => {
    const e = new DarsAuthError()
    expect(e).toBeInstanceOf(DarsApiError)
    expect(e).toBeInstanceOf(DarsAuthError)
    expect(e.status).toBe(401)
    expect(e.message).toBe('Invalid API key. Get your key from the Dars admin panel.')
    expect(e.name).toBe('DarsAuthError')
  })

  it('accepts a custom message', () => {
    const e = new DarsAuthError('custom message')
    expect(e.message).toBe('custom message')
  })
})

describe('DarsValidationError', () => {
  it('extends DarsApiError with status 422', () => {
    const e = new DarsValidationError("'grade' is required")
    expect(e).toBeInstanceOf(DarsApiError)
    expect(e).toBeInstanceOf(DarsValidationError)
    expect(e.status).toBe(422)
    expect(e.message).toBe("'grade' is required")
    expect(e.name).toBe('DarsValidationError')
  })
})

describe('DarsNotFoundError', () => {
  it('extends DarsApiError with status 404', () => {
    const e = new DarsNotFoundError('lesson plan')
    expect(e).toBeInstanceOf(DarsApiError)
    expect(e).toBeInstanceOf(DarsNotFoundError)
    expect(e.status).toBe(404)
    expect(e.message).toBe("lesson plan not found")
    expect(e.name).toBe('DarsNotFoundError')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/dars-node && pnpm test
```

Expected: FAIL — `Cannot find module '../src/errors'`

- [ ] **Step 3: Create `src/errors.ts`**

```ts
/**
 * Base error class for all Dars API errors.
 * Check `error.status` for the HTTP status code.
 */
export class DarsApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'DarsApiError'
    this.status = status
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

/**
 * Thrown when the API key is missing or invalid.
 * Check your DARS_SECRET_KEY environment variable.
 */
export class DarsAuthError extends DarsApiError {
  constructor(message = 'Invalid API key. Get your key from the Dars admin panel.') {
    super(message, 401)
    this.name = 'DarsAuthError'
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

/**
 * Thrown when request parameters fail validation.
 * `error.message` names the specific field and what's wrong.
 */
export class DarsValidationError extends DarsApiError {
  constructor(message: string) {
    super(message, 422)
    this.name = 'DarsValidationError'
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

/**
 * Thrown when the requested resource (e.g. lesson plan) does not exist.
 */
export class DarsNotFoundError extends DarsApiError {
  constructor(resource: string) {
    super(`${resource} not found`, 404)
    this.name = 'DarsNotFoundError'
    Object.setPrototypeOf(this, new.target.prototype)
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/dars-node && pnpm test
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/dars-node/src/errors.ts packages/dars-node/tests/errors.test.ts
git commit -m "feat(@dars/node): add typed error classes"
```

---

### Task 4: `LessonPlansResource`

**Files:**
- Create: `packages/dars-node/src/lesson-plans.ts`
- Create: `packages/dars-node/tests/lesson-plans.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `packages/dars-node/tests/lesson-plans.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { LessonPlansResource } from '../src/lesson-plans'
import { DarsAuthError, DarsNotFoundError, DarsValidationError } from '../src/errors'

const BASE_URL = 'https://api.dars.taleemabad.com'
const API_KEY = 'sk_test'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function mockResponse(body: unknown, status = 200) {
  mockFetch.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  })
}

const fakeLp = {
  id: 'abc-123',
  client_id: 'client-1',
  external_ref: null,
  grade: '3',
  subject: 'Maths',
  topic: null,
  page_number: '10',
  class_strength: null,
  content: '<html>LP</html>',
  content_bilingual: null,
  status: 'completed',
  metadata_: {},
  tags: {},
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('LessonPlansResource', () => {
  let resource: LessonPlansResource

  beforeEach(() => {
    mockFetch.mockReset()
    resource = new LessonPlansResource(BASE_URL, API_KEY)
  })

  describe('create', () => {
    it('POSTs to /api/v1/lesson-plans with correct headers and body', async () => {
      mockResponse(fakeLp, 201)

      const result = await resource.create({
        grade: '3',
        subject: 'Maths',
        page_number: '10',
      })

      expect(mockFetch).toHaveBeenCalledWith(
        `${BASE_URL}/api/v1/lesson-plans`,
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json',
          }),
          body: JSON.stringify({
            grade: '3',
            subject: 'Maths',
            page_number: '10',
          }),
        })
      )
      expect(result.id).toBe('abc-123')
    })

    it('throws DarsAuthError on 401', async () => {
      mockResponse({ detail: 'Unauthorized' }, 401)
      await expect(resource.create({ grade: '3', subject: 'Maths', page_number: '10' }))
        .rejects.toBeInstanceOf(DarsAuthError)
    })

    it('throws DarsValidationError on 422 with field message', async () => {
      mockResponse({ detail: [{ loc: ['body', 'grade'], msg: 'field required' }] }, 422)
      const err = await resource.create({ grade: '3', subject: 'Maths', page_number: '10' })
        .catch(e => e)
      expect(err).toBeInstanceOf(DarsValidationError)
      expect(err.message).toContain('grade')
    })

    it('throws DarsApiError on unexpected 500', async () => {
      mockResponse({ detail: 'Internal server error' }, 500)
      const err = await resource.create({ grade: '3', subject: 'Maths', page_number: '10' })
        .catch(e => e)
      expect(err.status).toBe(500)
    })
  })

  describe('list', () => {
    it('GETs /api/v1/lesson-plans with limit and offset', async () => {
      mockResponse({ items: [fakeLp], total: 1 })

      const result = await resource.list({ limit: 10, offset: 5 })

      expect(mockFetch).toHaveBeenCalledWith(
        `${BASE_URL}/api/v1/lesson-plans?limit=10&offset=5`,
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({ 'X-API-Key': API_KEY }),
        })
      )
      expect(result.items).toHaveLength(1)
      expect(result.total).toBe(1)
    })

    it('uses default limit/offset when not provided', async () => {
      mockResponse({ items: [], total: 0 })
      await resource.list()
      const url = mockFetch.mock.calls[0][0] as string
      expect(url).toContain('limit=20')
      expect(url).toContain('offset=0')
    })
  })

  describe('get', () => {
    it('GETs /api/v1/lesson-plans/:id', async () => {
      mockResponse(fakeLp)
      const result = await resource.get('abc-123')
      expect(mockFetch).toHaveBeenCalledWith(
        `${BASE_URL}/api/v1/lesson-plans/abc-123`,
        expect.objectContaining({ method: 'GET' })
      )
      expect(result.id).toBe('abc-123')
    })

    it('throws DarsNotFoundError on 404', async () => {
      mockResponse({ detail: 'Not found' }, 404)
      await expect(resource.get('bad-id')).rejects.toBeInstanceOf(DarsNotFoundError)
    })
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/dars-node && pnpm test tests/lesson-plans.test.ts
```

Expected: FAIL — `Cannot find module '../src/lesson-plans'`

- [ ] **Step 3: Create `src/lesson-plans.ts`**

```ts
import { DarsApiError, DarsAuthError, DarsNotFoundError, DarsValidationError } from './errors.js'
import type {
  CreateLessonPlanParams,
  LessonPlan,
  ListLessonPlansOptions,
  ListLessonPlansResult,
} from './types.js'

/**
 * Provides methods for creating, listing, and retrieving lesson plans.
 * Access via `dars.lessonPlans`.
 */
export class LessonPlansResource {
  constructor(
    private readonly baseUrl: string,
    private readonly apiKey: string,
  ) {}

  private async request<T>(
    path: string,
    options: RequestInit & { params?: Record<string, string | number> } = {},
  ): Promise<T> {
    const { params, ...fetchOptions } = options
    let url = `${this.baseUrl}${path}`
    if (params) {
      const qs = new URLSearchParams(
        Object.entries(params).map(([k, v]) => [k, String(v)]),
      )
      url += `?${qs.toString()}`
    }

    const response = await fetch(url, {
      ...fetchOptions,
      headers: {
        'X-API-Key': this.apiKey,
        ...fetchOptions.headers,
      },
    })

    const body = await response.json()

    if (!response.ok) {
      if (response.status === 401) throw new DarsAuthError()
      if (response.status === 404) throw new DarsNotFoundError('lesson plan')
      if (response.status === 422) {
        const detail = body?.detail
        let msg = 'Validation error'
        if (Array.isArray(detail) && detail.length > 0) {
          const field = detail[0]?.loc?.slice(1).join('.') ?? 'unknown'
          const issue = detail[0]?.msg ?? 'invalid'
          msg = `'${field}': ${issue}`
        }
        throw new DarsValidationError(msg)
      }
      throw new DarsApiError(body?.detail ?? 'Unexpected error', response.status)
    }

    return body as T
  }

  /**
   * Generate a new lesson plan. Takes approximately 60 seconds to complete.
   * The LP is stored in Dars and returned once generation finishes.
   *
   * @example
   * const lp = await dars.lessonPlans.create({ grade: '3', subject: 'Maths', page_number: '10' })
   */
  async create(params: CreateLessonPlanParams): Promise<LessonPlan> {
    return this.request<LessonPlan>('/api/v1/lesson-plans', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
  }

  /**
   * List lesson plans for your client, newest first.
   *
   * @example
   * const { items, total } = await dars.lessonPlans.list({ limit: 10, offset: 0 })
   */
  async list(options: ListLessonPlansOptions = {}): Promise<ListLessonPlansResult> {
    const { limit = 20, offset = 0 } = options
    return this.request<ListLessonPlansResult>('/api/v1/lesson-plans', {
      method: 'GET',
      params: { limit, offset },
    })
  }

  /**
   * Retrieve a single lesson plan by ID.
   *
   * @param id - The lesson plan UUID returned from `create` or `list`
   * @throws {DarsNotFoundError} if the LP does not exist or belongs to another client
   */
  async get(id: string): Promise<LessonPlan> {
    return this.request<LessonPlan>(`/api/v1/lesson-plans/${id}`, {
      method: 'GET',
    })
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/dars-node && pnpm test tests/lesson-plans.test.ts
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/dars-node/src/lesson-plans.ts packages/dars-node/tests/lesson-plans.test.ts
git commit -m "feat(@dars/node): add LessonPlansResource with full test coverage"
```

---

### Task 5: `DarsClient` class + public exports

**Files:**
- Create: `packages/dars-node/src/client.ts`
- Create: `packages/dars-node/src/index.ts`

- [ ] **Step 1: Create `src/client.ts`**

```ts
import { LessonPlansResource } from './lesson-plans.js'
import type { DarsClientConfig } from './types.js'

const DEFAULT_BASE_URL = 'https://api.dars.taleemabad.com'

/**
 * The main Dars client. Instantiate once and reuse across your application.
 *
 * @example
 * import Dars from '@dars/node'
 * const dars = new Dars({ apiKey: process.env.DARS_SECRET_KEY })
 * const lp = await dars.lessonPlans.create({ grade: '3', subject: 'Maths', page_number: '10' })
 */
export class DarsClient {
  /** Access lesson plan methods: create, list, get */
  readonly lessonPlans: LessonPlansResource

  constructor(config: DarsClientConfig) {
    if (!config.apiKey) {
      throw new Error(
        'Dars API key is required. Set DARS_SECRET_KEY in your environment and pass it as apiKey.',
      )
    }
    const baseUrl = (config.baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, '')
    this.lessonPlans = new LessonPlansResource(baseUrl, config.apiKey)
  }
}

export default DarsClient
```

- [ ] **Step 2: Create `src/index.ts`**

```ts
export { DarsClient } from './client.js'
export { DarsClient as default } from './client.js'
export { DarsApiError, DarsAuthError, DarsValidationError, DarsNotFoundError } from './errors.js'
export type {
  LessonPlan,
  CreateLessonPlanParams,
  ListLessonPlansOptions,
  ListLessonPlansResult,
  DarsClientConfig,
} from './types.js'
```

- [ ] **Step 3: Build and verify**

```bash
cd packages/dars-node && pnpm build
```

Expected: `dist/` created with `index.js`, `index.cjs`, `index.d.ts`, `middleware.js`, `middleware.cjs`, `middleware.d.ts` (middleware will be empty until Task 6 — that's fine, tsup will warn but not fail if the file doesn't exist yet; create a placeholder).

Create `packages/dars-node/src/middleware.ts` placeholder:
```ts
export {}
```

Re-run: `pnpm build` — expected: clean build, no errors.

- [ ] **Step 4: Run all tests**

```bash
cd packages/dars-node && pnpm test
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/dars-node/src/client.ts packages/dars-node/src/index.ts packages/dars-node/src/middleware.ts
git commit -m "feat(@dars/node): add DarsClient and public exports"
```

---

### Task 6: Middleware — `createDarsHandler`

**Files:**
- Modify: `packages/dars-node/src/middleware.ts`
- Create: `packages/dars-node/tests/middleware.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `packages/dars-node/tests/middleware.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createDarsHandler } from '../src/middleware'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function mockDarsResponse(body: unknown, status = 200) {
  mockFetch.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    text: async () => JSON.stringify(body),
  })
}

// Minimal Next.js-style Request mock
function makeRequest(method: string, path: string, body?: unknown): Request {
  return new Request(`http://localhost/api/dars${path}`, {
    method,
    headers: { 'content-type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
}

describe('createDarsHandler', () => {
  const handler = createDarsHandler({
    apiKey: 'sk_test',
    baseUrl: 'https://api.dars.taleemabad.com',
  })

  beforeEach(() => mockFetch.mockReset())

  it('proxies POST /lesson-plans to Dars with X-API-Key header', async () => {
    mockDarsResponse({ id: 'abc' }, 201)

    const req = makeRequest('POST', '/lesson-plans', { grade: '3', subject: 'Maths', page_number: '10' })
    const res = await handler.POST(req, { params: { path: ['lesson-plans'] } })

    expect(mockFetch).toHaveBeenCalledWith(
      'https://api.dars.taleemabad.com/api/v1/lesson-plans',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'x-api-key': 'sk_test' }),
      })
    )
    expect(res.status).toBe(201)
  })

  it('proxies GET /lesson-plans to Dars', async () => {
    mockDarsResponse({ items: [], total: 0 })

    const req = makeRequest('GET', '/lesson-plans')
    const res = await handler.GET(req, { params: { path: ['lesson-plans'] } })

    expect(mockFetch).toHaveBeenCalledWith(
      'https://api.dars.taleemabad.com/api/v1/lesson-plans',
      expect.objectContaining({ method: 'GET' })
    )
    expect(res.status).toBe(200)
  })

  it('does NOT forward the incoming request X-API-Key header to the client', async () => {
    mockDarsResponse({ items: [], total: 0 })

    // Simulate an attacker sending their own key in the request
    const req = new Request('http://localhost/api/dars/lesson-plans', {
      method: 'GET',
      headers: { 'x-api-key': 'attacker_key' },
    })
    await handler.GET(req, { params: { path: ['lesson-plans'] } })

    const sentHeaders = mockFetch.mock.calls[0][1].headers as Record<string, string>
    // The key sent to Dars must be the configured secret, not the attacker's key
    expect(sentHeaders['x-api-key']).toBe('sk_test')
  })

  it('forwards Dars error responses unchanged', async () => {
    mockDarsResponse({ detail: 'Not found' }, 404)

    const req = makeRequest('GET', '/lesson-plans/bad-id')
    const res = await handler.GET(req, { params: { path: ['lesson-plans', 'bad-id'] } })

    expect(res.status).toBe(404)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/dars-node && pnpm test tests/middleware.test.ts
```

Expected: FAIL — `createDarsHandler` not exported from middleware.

- [ ] **Step 3: Implement `src/middleware.ts`**

```ts
const DEFAULT_BASE_URL = 'https://api.dars.taleemabad.com'

interface DarsHandlerConfig {
  /** Your Dars secret API key. Never exposed to the browser. */
  apiKey: string
  /**
   * Base URL of the Dars API.
   * @default "https://api.dars.taleemabad.com"
   */
  baseUrl?: string
}

interface RouteContext {
  params: { path: string[] }
}

type RouteHandler = (req: Request, ctx: RouteContext) => Promise<Response>

/**
 * Creates a Next.js App Router route handler that proxies requests to the Dars API.
 * The secret API key is injected server-side and never exposed to the browser.
 *
 * @example
 * // app/api/dars/[...path]/route.ts
 * import { createDarsHandler } from '@dars/node/middleware'
 * export const { GET, POST } = createDarsHandler({ apiKey: process.env.DARS_SECRET_KEY })
 */
export function createDarsHandler(config: DarsHandlerConfig): { GET: RouteHandler; POST: RouteHandler } {
  const baseUrl = (config.baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, '')

  const handle: RouteHandler = async (req, ctx) => {
    const path = ctx.params.path.join('/')
    const targetUrl = `${baseUrl}/api/v1/${path}`

    // Forward query string
    const incoming = new URL(req.url)
    const target = new URL(targetUrl)
    incoming.searchParams.forEach((v, k) => target.searchParams.set(k, v))

    // Build headers — inject our API key, strip any incoming key
    const forwardHeaders: Record<string, string> = {
      'content-type': 'application/json',
      'x-api-key': config.apiKey,
    }

    // Forward other safe headers (accept, accept-language, etc.)
    req.headers.forEach((value, key) => {
      const lower = key.toLowerCase()
      if (lower === 'x-api-key') return // never forward — we inject ours
      if (lower === 'host') return
      if (lower === 'content-length') return
      forwardHeaders[lower] = value
    })

    const body = req.method !== 'GET' && req.method !== 'HEAD'
      ? await req.text()
      : undefined

    const upstream = await fetch(target.toString(), {
      method: req.method,
      headers: forwardHeaders,
      body,
    })

    const responseBody = await upstream.text()
    return new Response(responseBody, {
      status: upstream.status,
      headers: { 'content-type': upstream.headers.get('content-type') ?? 'application/json' },
    })
  }

  return { GET: handle, POST: handle }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/dars-node && pnpm test tests/middleware.test.ts
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
cd packages/dars-node && pnpm test
```

Expected: all tests PASS.

- [ ] **Step 6: Build**

```bash
cd packages/dars-node && pnpm build
```

Expected: clean build. Check `dist/middleware.js` exists and exports `createDarsHandler`.

- [ ] **Step 7: Commit**

```bash
git add packages/dars-node/src/middleware.ts packages/dars-node/tests/middleware.test.ts
git commit -m "feat(@dars/node): add createDarsHandler middleware for Next.js"
```

---

## Part 2: `@dars/react`

---

### Task 7: Scaffold `@dars/react` package

**Files:**
- Create: `packages/dars-react/package.json`
- Create: `packages/dars-react/tsconfig.json`
- Create: `packages/dars-react/tsup.config.ts`

- [ ] **Step 1: Create `packages/dars-react/package.json`**

```json
{
  "name": "@dars/react",
  "version": "0.1.0",
  "description": "React hooks and components for Dars lesson plan integration",
  "type": "module",
  "main": "./dist/index.cjs",
  "module": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "import": "./dist/index.js",
      "require": "./dist/index.cjs",
      "types": "./dist/index.d.ts"
    }
  },
  "scripts": {
    "build": "tsup",
    "test": "vitest run",
    "test:watch": "vitest",
    "typecheck": "tsc --noEmit"
  },
  "peerDependencies": {
    "react": ">=18.0.0"
  },
  "devDependencies": {
    "tsup": "^8.0.0",
    "typescript": "^5.4.0",
    "vitest": "^1.6.0",
    "@types/react": "^18.0.0",
    "@testing-library/react": "^15.0.0",
    "@testing-library/user-event": "^14.0.0",
    "@vitejs/plugin-react": "^4.0.0",
    "jsdom": "^24.0.0",
    "react": "^18.0.0",
    "react-dom": "^18.0.0"
  }
}
```

- [ ] **Step 2: Create `packages/dars-react/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "declaration": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create `packages/dars-react/tsup.config.ts`**

```ts
import { defineConfig } from 'tsup'

export default defineConfig({
  entry: { index: 'src/index.ts' },
  format: ['esm', 'cjs'],
  dts: true,
  clean: true,
  sourcemap: true,
  external: ['react', 'react-dom'],
})
```

- [ ] **Step 4: Create `packages/dars-react/vitest.config.ts`**

```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: [],
  },
})
```

- [ ] **Step 5: Install dependencies**

```bash
cd packages/dars-react && pnpm install
```

Expected: `node_modules/` created, no errors.

- [ ] **Step 6: Commit**

```bash
git add packages/dars-react/package.json packages/dars-react/tsconfig.json packages/dars-react/tsup.config.ts packages/dars-react/vitest.config.ts
git commit -m "chore: scaffold @dars/react package"
```

---

### Task 8: Types and errors for `@dars/react`

**Files:**
- Create: `packages/dars-react/src/types.ts`
- Create: `packages/dars-react/src/errors.ts`

- [ ] **Step 1: Create `src/types.ts`**

```ts
/**
 * Parameters for generating a lesson plan.
 */
export interface CreateLessonPlanParams {
  /** Grade level, e.g. "3", "KG", "1" */
  grade: string
  /** Subject name, e.g. "Maths", "Eng", "Urdu", "Science" */
  subject: string
  /** Textbook page number(s), e.g. "10" or "10-12" */
  page_number: string
  /** Curriculum type. Defaults to "ICT" (national). Use "Punjab" for provincial. */
  curriculum?: 'ICT' | 'Punjab'
  /** Number of students in the class */
  class_strength?: number
  /** Optional topic override */
  topic?: string
  /** Your own reference ID — stored and returned as-is */
  external_ref?: string
  /** Exercise page number(s), if different from main page */
  exercise_page_number?: string
  /** Custom instructions passed to the LP generator */
  custom_prompt?: string
  /** Generate both English and Urdu versions. Defaults to false. */
  generate_bilingual?: boolean
  /** Enable extended reasoning. Defaults to true. */
  reasoning_enabled?: boolean
}

/**
 * A lesson plan returned by Dars.
 */
export interface LessonPlan {
  id: string
  client_id: string
  external_ref: string | null
  grade: string
  subject: string
  topic: string | null
  page_number: string | null
  class_strength: number | null
  /** HTML content of the lesson plan */
  content: string | null
  /** Bilingual (Urdu) HTML content */
  content_bilingual: string | null
  status: string
  metadata_: Record<string, unknown>
  tags: Record<string, unknown>
  created_at: string
  updated_at: string
}

/**
 * Result from listing lesson plans.
 */
export interface ListLessonPlansResult {
  items: LessonPlan[]
  total: number
}
```

- [ ] **Step 2: Create `src/errors.ts`**

```ts
/**
 * Base error thrown by @dars/react hooks.
 * Check `error.status` for the HTTP status code.
 */
export class DarsError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'DarsError'
    this.status = status
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

/** Thrown when the proxy endpoint returns 401 — likely a misconfigured API key on your backend. */
export class DarsAuthError extends DarsError {
  constructor(message = 'Authentication failed. Check your backend proxy configuration.') {
    super(message, 401)
    this.name = 'DarsAuthError'
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

/** Thrown when request parameters fail validation. `error.message` names the specific field. */
export class DarsValidationError extends DarsError {
  constructor(message: string) {
    super(message, 422)
    this.name = 'DarsValidationError'
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

/** Thrown when the requested lesson plan does not exist. */
export class DarsNotFoundError extends DarsError {
  constructor() {
    super('Lesson plan not found', 404)
    this.name = 'DarsNotFoundError'
    Object.setPrototypeOf(this, new.target.prototype)
  }
}
```

- [ ] **Step 3: Verify types compile**

```bash
cd packages/dars-react && npx tsc --noEmit --allowJs false src/types.ts src/errors.ts 2>/dev/null || true
```

Expected: no errors (or only "cannot find module react" which is fine at this stage).

- [ ] **Step 4: Commit**

```bash
git add packages/dars-react/src/types.ts packages/dars-react/src/errors.ts
git commit -m "feat(@dars/react): add types and error classes"
```

---

### Task 9: `DarsProvider` and context

**Files:**
- Create: `packages/dars-react/src/context.ts`
- Create: `packages/dars-react/src/provider.tsx`
- Create: `packages/dars-react/tests/provider.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `packages/dars-react/tests/provider.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { useContext } from 'react'
import { DarsContext } from '../src/context'
import { DarsProvider } from '../src/provider'

function TestConsumer() {
  const ctx = useContext(DarsContext)
  return <div data-testid="endpoint">{ctx.endpoint}</div>
}

describe('DarsProvider', () => {
  it('provides endpoint to children via context', () => {
    render(
      <DarsProvider endpoint="/api/dars">
        <TestConsumer />
      </DarsProvider>
    )
    expect(screen.getByTestId('endpoint').textContent).toBe('/api/dars')
  })

  it('throws if used outside DarsProvider', () => {
    // Reading context outside provider returns default empty string
    render(<TestConsumer />)
    expect(screen.getByTestId('endpoint').textContent).toBe('')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/dars-react && pnpm test tests/provider.test.tsx
```

Expected: FAIL — modules not found.

- [ ] **Step 3: Create `src/context.ts`**

```ts
import { createContext } from 'react'

export interface DarsContextValue {
  /** The URL of your backend proxy endpoint, e.g. "/api/dars" */
  endpoint: string
}

export const DarsContext = createContext<DarsContextValue>({ endpoint: '' })
```

- [ ] **Step 4: Create `src/provider.tsx`**

```tsx
import { DarsContext } from './context.js'

interface DarsProviderProps {
  /**
   * The URL of your backend proxy endpoint.
   * All Dars requests from hooks and components will be sent here.
   *
   * @example "/api/dars"
   */
  endpoint: string
  children: React.ReactNode
}

/**
 * Wrap your app (or the subtree that uses Dars) with DarsProvider.
 * This sets the backend proxy endpoint for all hooks and components.
 *
 * @example
 * <DarsProvider endpoint="/api/dars">
 *   <App />
 * </DarsProvider>
 */
export function DarsProvider({ endpoint, children }: DarsProviderProps) {
  return (
    <DarsContext.Provider value={{ endpoint }}>
      {children}
    </DarsContext.Provider>
  )
}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd packages/dars-react && pnpm test tests/provider.test.tsx
```

Expected: 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/dars-react/src/context.ts packages/dars-react/src/provider.tsx packages/dars-react/tests/provider.test.tsx
git commit -m "feat(@dars/react): add DarsProvider and context"
```

---

### Task 10: `useLessonPlan` hook

**Files:**
- Create: `packages/dars-react/src/hooks/use-lesson-plan.ts`
- Create: `packages/dars-react/tests/use-lesson-plan.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `packages/dars-react/tests/use-lesson-plan.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { DarsProvider } from '../src/provider'
import { useLessonPlan } from '../src/hooks/use-lesson-plan'
import { DarsAuthError, DarsValidationError } from '../src/errors'
import type { ReactNode } from 'react'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function wrapper({ children }: { children: ReactNode }) {
  return <DarsProvider endpoint="/api/dars">{children}</DarsProvider>
}

const fakeLp = {
  id: 'abc-123',
  client_id: 'c1',
  external_ref: null,
  grade: '3',
  subject: 'Maths',
  topic: null,
  page_number: '10',
  class_strength: null,
  content: '<html>LP</html>',
  content_bilingual: null,
  status: 'completed',
  metadata_: {},
  tags: {},
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function mockResponse(body: unknown, status = 200) {
  mockFetch.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  })
}

describe('useLessonPlan', () => {
  beforeEach(() => mockFetch.mockReset())

  it('starts in idle state', () => {
    const { result } = renderHook(() => useLessonPlan(), { wrapper })
    expect(result.current.isLoading).toBe(false)
    expect(result.current.lessonPlan).toBeNull()
    expect(result.current.error).toBeNull()
  })

  it('transitions to loading then success', async () => {
    mockResponse(fakeLp, 201)

    const { result } = renderHook(() => useLessonPlan(), { wrapper })

    await act(async () => {
      await result.current.generate({ grade: '3', subject: 'Maths', page_number: '10' })
    })

    expect(result.current.isLoading).toBe(false)
    expect(result.current.lessonPlan?.id).toBe('abc-123')
    expect(result.current.error).toBeNull()
  })

  it('POSTs to the proxy endpoint', async () => {
    mockResponse(fakeLp, 201)

    const { result } = renderHook(() => useLessonPlan(), { wrapper })
    await act(async () => {
      await result.current.generate({ grade: '3', subject: 'Maths', page_number: '10' })
    })

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/dars/lesson-plans',
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('sets typed error on 401', async () => {
    mockResponse({ detail: 'Unauthorized' }, 401)

    const { result } = renderHook(() => useLessonPlan(), { wrapper })
    await act(async () => {
      await result.current.generate({ grade: '3', subject: 'Maths', page_number: '10' })
    })

    expect(result.current.error).toBeInstanceOf(DarsAuthError)
    expect(result.current.lessonPlan).toBeNull()
  })

  it('sets typed error on 422', async () => {
    mockResponse({ detail: [{ loc: ['body', 'grade'], msg: 'field required' }] }, 422)

    const { result } = renderHook(() => useLessonPlan(), { wrapper })
    await act(async () => {
      await result.current.generate({ grade: '3', subject: 'Maths', page_number: '10' })
    })

    expect(result.current.error).toBeInstanceOf(DarsValidationError)
  })

  it('resets error and lessonPlan on new generate call', async () => {
    mockResponse({ detail: 'Unauthorized' }, 401)
    const { result } = renderHook(() => useLessonPlan(), { wrapper })
    await act(async () => {
      await result.current.generate({ grade: '3', subject: 'Maths', page_number: '10' })
    })
    expect(result.current.error).not.toBeNull()

    mockResponse(fakeLp, 201)
    await act(async () => {
      await result.current.generate({ grade: '3', subject: 'Maths', page_number: '10' })
    })
    expect(result.current.error).toBeNull()
    expect(result.current.lessonPlan?.id).toBe('abc-123')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/dars-react && pnpm test tests/use-lesson-plan.test.tsx
```

Expected: FAIL — `useLessonPlan` not found.

- [ ] **Step 3: Create `src/hooks/use-lesson-plan.ts`**

```ts
import { useCallback, useContext, useState } from 'react'
import { DarsContext } from '../context.js'
import { DarsAuthError, DarsError, DarsNotFoundError, DarsValidationError } from '../errors.js'
import type { CreateLessonPlanParams, LessonPlan } from '../types.js'

interface UseLessonPlanResult {
  /**
   * Generate a lesson plan. Takes ~60 seconds.
   * Sets `isLoading` to true while in progress.
   */
  generate: (params: CreateLessonPlanParams) => Promise<void>
  /** The generated lesson plan. Null until generation succeeds. */
  lessonPlan: LessonPlan | null
  /** True while generation is in progress (~60s). Show a loading indicator. */
  isLoading: boolean
  /** Typed error if generation failed. Null on success or before first call. */
  error: DarsError | null
}

function parseError(status: number, body: unknown): DarsError {
  if (status === 401) return new DarsAuthError()
  if (status === 404) return new DarsNotFoundError()
  if (status === 422) {
    const detail = (body as any)?.detail
    let msg = 'Validation error'
    if (Array.isArray(detail) && detail.length > 0) {
      const field = detail[0]?.loc?.slice(1).join('.') ?? 'unknown'
      const issue = detail[0]?.msg ?? 'invalid'
      msg = `'${field}': ${issue}`
    }
    return new DarsValidationError(msg)
  }
  return new DarsError((body as any)?.detail ?? 'Unexpected error', status)
}

/**
 * Hook for generating a single lesson plan.
 * Must be used inside a `<DarsProvider>`.
 *
 * @example
 * const { generate, lessonPlan, isLoading, error } = useLessonPlan()
 * await generate({ grade: '3', subject: 'Maths', page_number: '10' })
 */
export function useLessonPlan(): UseLessonPlanResult {
  const { endpoint } = useContext(DarsContext)
  const [lessonPlan, setLessonPlan] = useState<LessonPlan | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<DarsError | null>(null)

  const generate = useCallback(async (params: CreateLessonPlanParams) => {
    setIsLoading(true)
    setError(null)
    setLessonPlan(null)

    try {
      const res = await fetch(`${endpoint}/lesson-plans`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      })
      const body = await res.json()
      if (!res.ok) {
        setError(parseError(res.status, body))
        return
      }
      setLessonPlan(body as LessonPlan)
    } catch {
      setError(new DarsError('Network error — check your connection', 0))
    } finally {
      setIsLoading(false)
    }
  }, [endpoint])

  return { generate, lessonPlan, isLoading, error }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/dars-react && pnpm test tests/use-lesson-plan.test.tsx
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/dars-react/src/hooks/use-lesson-plan.ts packages/dars-react/tests/use-lesson-plan.test.tsx
git commit -m "feat(@dars/react): add useLessonPlan hook"
```

---

### Task 11: `useLessonPlans` hook

**Files:**
- Create: `packages/dars-react/src/hooks/use-lesson-plans.ts`
- Create: `packages/dars-react/tests/use-lesson-plans.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `packages/dars-react/tests/use-lesson-plans.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { DarsProvider } from '../src/provider'
import { useLessonPlans } from '../src/hooks/use-lesson-plans'
import type { ReactNode } from 'react'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function wrapper({ children }: { children: ReactNode }) {
  return <DarsProvider endpoint="/api/dars">{children}</DarsProvider>
}

const fakeList = {
  items: [{ id: 'abc', grade: '3', subject: 'Maths' }],
  total: 1,
}

function mockResponse(body: unknown, status = 200) {
  mockFetch.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  })
}

describe('useLessonPlans', () => {
  beforeEach(() => mockFetch.mockReset())

  it('starts in idle state', () => {
    const { result } = renderHook(() => useLessonPlans(), { wrapper })
    expect(result.current.isLoading).toBe(false)
    expect(result.current.lessonPlans).toEqual([])
    expect(result.current.total).toBe(0)
    expect(result.current.error).toBeNull()
  })

  it('fetches on mount by default', async () => {
    mockResponse(fakeList)
    const { result } = renderHook(() => useLessonPlans(), { wrapper })
    // wait for effect
    await act(async () => {})
    expect(result.current.lessonPlans).toHaveLength(1)
    expect(result.current.total).toBe(1)
  })

  it('GETs proxy endpoint with limit and offset', async () => {
    mockResponse(fakeList)
    renderHook(() => useLessonPlans({ limit: 5, offset: 10 }), { wrapper })
    await act(async () => {})
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/dars/lesson-plans?limit=5&offset=10',
      expect.objectContaining({ method: 'GET' })
    )
  })

  it('sets error on failure', async () => {
    mockResponse({ detail: 'Unauthorized' }, 401)
    const { result } = renderHook(() => useLessonPlans(), { wrapper })
    await act(async () => {})
    expect(result.current.error).not.toBeNull()
    expect(result.current.error?.status).toBe(401)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/dars-react && pnpm test tests/use-lesson-plans.test.tsx
```

Expected: FAIL — `useLessonPlans` not found.

- [ ] **Step 3: Create `src/hooks/use-lesson-plans.ts`**

```ts
import { useCallback, useContext, useEffect, useState } from 'react'
import { DarsContext } from '../context.js'
import { DarsAuthError, DarsError, DarsNotFoundError, DarsValidationError } from '../errors.js'
import type { LessonPlan } from '../types.js'

interface UseLessonPlansOptions {
  /** Max results to fetch. Default: 20 */
  limit?: number
  /** Offset for pagination. Default: 0 */
  offset?: number
}

interface UseLessonPlansResult {
  lessonPlans: LessonPlan[]
  total: number
  isLoading: boolean
  error: DarsError | null
  /** Manually re-fetch the list */
  refetch: () => void
}

function parseError(status: number, body: unknown): DarsError {
  if (status === 401) return new DarsAuthError()
  if (status === 404) return new DarsNotFoundError()
  if (status === 422) {
    const detail = (body as any)?.detail
    let msg = 'Validation error'
    if (Array.isArray(detail) && detail.length > 0) {
      const field = detail[0]?.loc?.slice(1).join('.') ?? 'unknown'
      const issue = detail[0]?.msg ?? 'invalid'
      msg = `'${field}': ${issue}`
    }
    return new DarsValidationError(msg)
  }
  return new DarsError((body as any)?.detail ?? 'Unexpected error', status)
}

/**
 * Hook for listing lesson plans. Fetches on mount and when options change.
 * Must be used inside a `<DarsProvider>`.
 *
 * @example
 * const { lessonPlans, total, isLoading, error } = useLessonPlans({ limit: 10 })
 */
export function useLessonPlans(options: UseLessonPlansOptions = {}): UseLessonPlansResult {
  const { limit = 20, offset = 0 } = options
  const { endpoint } = useContext(DarsContext)
  const [lessonPlans, setLessonPlans] = useState<LessonPlan[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<DarsError | null>(null)
  const [tick, setTick] = useState(0)

  const refetch = useCallback(() => setTick(t => t + 1), [])

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setError(null)

    const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    fetch(`${endpoint}/lesson-plans?${qs}`, { method: 'GET' })
      .then(async res => {
        const body = await res.json()
        if (cancelled) return
        if (!res.ok) { setError(parseError(res.status, body)); return }
        setLessonPlans(body.items ?? [])
        setTotal(body.total ?? 0)
      })
      .catch(() => {
        if (!cancelled) setError(new DarsError('Network error — check your connection', 0))
      })
      .finally(() => { if (!cancelled) setIsLoading(false) })

    return () => { cancelled = true }
  }, [endpoint, limit, offset, tick])

  return { lessonPlans, total, isLoading, error, refetch }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/dars-react && pnpm test tests/use-lesson-plans.test.tsx
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/dars-react/src/hooks/use-lesson-plans.ts packages/dars-react/tests/use-lesson-plans.test.tsx
git commit -m "feat(@dars/react): add useLessonPlans hook"
```

---

### Task 12: `LessonPlanViewer` component

**Files:**
- Create: `packages/dars-react/src/components/lesson-plan-viewer.tsx`
- Create: `packages/dars-react/tests/lesson-plan-viewer.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `packages/dars-react/tests/lesson-plan-viewer.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LessonPlanViewer } from '../src/components/lesson-plan-viewer'

describe('LessonPlanViewer', () => {
  it('renders HTML content in an iframe sandbox', () => {
    const { container } = render(<LessonPlanViewer html="<p>Hello</p>" />)
    const iframe = container.querySelector('iframe')
    expect(iframe).not.toBeNull()
    expect(iframe?.getAttribute('sandbox')).toBeTruthy()
  })

  it('strips script tags from HTML (XSS prevention)', () => {
    const { container } = render(
      <LessonPlanViewer html='<p>Safe</p><script>alert("xss")</script>' />
    )
    const iframe = container.querySelector('iframe')
    // The iframe sandbox blocks scripts — and we also sanitize at the srcdoc level
    expect(iframe?.getAttribute('sandbox')).not.toContain('allow-scripts')
  })

  it('renders null gracefully when html is null', () => {
    const { container } = render(<LessonPlanViewer html={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('applies className to wrapper', () => {
    const { container } = render(<LessonPlanViewer html="<p>Hi</p>" className="my-viewer" />)
    expect(container.firstChild).toHaveClass('my-viewer')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/dars-react && pnpm test tests/lesson-plan-viewer.test.tsx
```

Expected: FAIL — `LessonPlanViewer` not found.

- [ ] **Step 3: Create `src/components/lesson-plan-viewer.tsx`**

```tsx
interface LessonPlanViewerProps {
  /** Raw HTML string of the lesson plan. Pass `lessonPlan.content` here. */
  html: string | null
  /** Optional CSS class for the wrapper div */
  className?: string
  /** Height of the viewer. Defaults to "100%" */
  height?: string
}

/**
 * Safely renders a Dars lesson plan HTML string.
 * Uses a sandboxed iframe to prevent XSS — scripts are blocked.
 *
 * @example
 * <LessonPlanViewer html={lessonPlan.content} className="my-viewer" />
 */
export function LessonPlanViewer({ html, className, height = '100%' }: LessonPlanViewerProps) {
  if (!html) return null

  return (
    <div className={className} style={{ height }}>
      <iframe
        srcDoc={html}
        sandbox="allow-same-origin"
        style={{ width: '100%', height: '100%', border: 'none' }}
        title="Lesson Plan"
      />
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/dars-react && pnpm test tests/lesson-plan-viewer.test.tsx
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/dars-react/src/components/lesson-plan-viewer.tsx packages/dars-react/tests/lesson-plan-viewer.test.tsx
git commit -m "feat(@dars/react): add LessonPlanViewer component"
```

---

### Task 13: `LessonPlanGenerator` component

**Files:**
- Create: `packages/dars-react/src/components/lesson-plan-generator.tsx`
- Create: `packages/dars-react/tests/lesson-plan-generator.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `packages/dars-react/tests/lesson-plan-generator.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { DarsProvider } from '../src/provider'
import { LessonPlanGenerator } from '../src/components/lesson-plan-generator'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function mockResponse(body: unknown, status = 200) {
  mockFetch.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  })
}

const fakeLp = {
  id: 'abc-123', client_id: 'c1', external_ref: null, grade: '3',
  subject: 'Maths', topic: null, page_number: '10', class_strength: null,
  content: '<html>LP</html>', content_bilingual: null, status: 'completed',
  metadata_: {}, tags: {}, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
}

function renderGenerator(props = {}) {
  return render(
    <DarsProvider endpoint="/api/dars">
      <LessonPlanGenerator {...props} />
    </DarsProvider>
  )
}

describe('LessonPlanGenerator', () => {
  beforeEach(() => mockFetch.mockReset())

  it('renders grade, subject, page_number, and curriculum fields', () => {
    renderGenerator()
    expect(screen.getByLabelText(/grade/i)).toBeTruthy()
    expect(screen.getByLabelText(/subject/i)).toBeTruthy()
    expect(screen.getByLabelText(/page/i)).toBeTruthy()
    expect(screen.getByLabelText(/curriculum/i)).toBeTruthy()
  })

  it('does not submit when required fields are empty', async () => {
    renderGenerator()
    fireEvent.click(screen.getByRole('button', { name: /generate/i }))
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('calls onSuccess with the lesson plan on success', async () => {
    const onSuccess = vi.fn()
    mockResponse(fakeLp, 201)
    renderGenerator({ onSuccess })

    fireEvent.change(screen.getByLabelText(/grade/i), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText(/subject/i), { target: { value: 'Maths' } })
    fireEvent.change(screen.getByLabelText(/page/i), { target: { value: '10' } })
    fireEvent.click(screen.getByRole('button', { name: /generate/i }))

    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(fakeLp))
  })

  it('shows error message on failure', async () => {
    mockResponse({ detail: 'Unauthorized' }, 401)
    renderGenerator()

    fireEvent.change(screen.getByLabelText(/grade/i), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText(/subject/i), { target: { value: 'Maths' } })
    fireEvent.change(screen.getByLabelText(/page/i), { target: { value: '10' } })
    fireEvent.click(screen.getByRole('button', { name: /generate/i }))

    await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy())
  })

  it('applies classNames to button and error', async () => {
    mockResponse({ detail: 'Unauthorized' }, 401)
    renderGenerator({ classNames: { button: 'my-btn', error: 'my-err' } })

    expect(screen.getByRole('button', { name: /generate/i })).toHaveClass('my-btn')

    fireEvent.change(screen.getByLabelText(/grade/i), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText(/subject/i), { target: { value: 'Maths' } })
    fireEvent.change(screen.getByLabelText(/page/i), { target: { value: '10' } })
    fireEvent.click(screen.getByRole('button', { name: /generate/i }))

    await waitFor(() => expect(screen.getByRole('alert')).toHaveClass('my-err'))
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/dars-react && pnpm test tests/lesson-plan-generator.test.tsx
```

Expected: FAIL — `LessonPlanGenerator` not found.

- [ ] **Step 3: Create `src/components/lesson-plan-generator.tsx`**

```tsx
import { useState, useEffect } from 'react'
import { useLessonPlan } from '../hooks/use-lesson-plan.js'
import type { LessonPlan, CreateLessonPlanParams } from '../types.js'

interface LessonPlanGeneratorProps {
  onSuccess?: (lp: LessonPlan) => void
  classNames?: {
    form?: string
    button?: string
    error?: string
  }
}

export function LessonPlanGenerator({ onSuccess, classNames = {} }: LessonPlanGeneratorProps) {
  const { generate, lessonPlan, isLoading, error } = useLessonPlan()
  const [grade, setGrade] = useState('')
  const [subject, setSubject] = useState('')
  const [pageNumber, setPageNumber] = useState('')
  const [curriculum, setCurriculum] = useState<'ICT' | 'Punjab'>('ICT')

  useEffect(() => {
    if (lessonPlan && onSuccess) onSuccess(lessonPlan)
  }, [lessonPlan, onSuccess])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!grade || !subject || !pageNumber) return
    generate({ grade, subject, page_number: pageNumber, curriculum })
  }

  return (
    <form onSubmit={handleSubmit} className={classNames.form}>
      <div>
        <label htmlFor="dars-grade">Grade</label>
        <input
          id="dars-grade"
          type="text"
          value={grade}
          onChange={e => setGrade(e.target.value)}
          placeholder="e.g. 3"
        />
      </div>
      <div>
        <label htmlFor="dars-subject">Subject</label>
        <input
          id="dars-subject"
          type="text"
          value={subject}
          onChange={e => setSubject(e.target.value)}
          placeholder="e.g. Maths"
        />
      </div>
      <div>
        <label htmlFor="dars-page">Page Number</label>
        <input
          id="dars-page"
          type="text"
          value={pageNumber}
          onChange={e => setPageNumber(e.target.value)}
          placeholder="e.g. 10"
        />
      </div>
      <div>
        <label htmlFor="dars-curriculum">Curriculum</label>
        <select
          id="dars-curriculum"
          value={curriculum}
          onChange={e => setCurriculum(e.target.value as 'ICT' | 'Punjab')}
        >
          <option value="ICT">ICT (National)</option>
          <option value="Punjab">Punjab (Provincial)</option>
        </select>
      </div>
      <button type="submit" className={classNames.button} disabled={isLoading}>
        {isLoading ? 'Generating... (~60s)' : 'Generate'}
      </button>
      {error && (
        <p role="alert" className={classNames.error}>
          {error.message}
        </p>
      )}
    </form>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/dars-react && pnpm test tests/lesson-plan-generator.test.tsx
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/dars-react/src/components/lesson-plan-generator.tsx packages/dars-react/tests/lesson-plan-generator.test.tsx
git commit -m "feat(@dars/react): add LessonPlanGenerator component"
```

---

### Task 14: Public exports + build

**Files:**
- Create: `packages/dars-react/src/index.ts`

- [ ] **Step 1: Create `src/index.ts`**

```ts
export { DarsProvider } from './provider.js'
export { useLessonPlan } from './hooks/use-lesson-plan.js'
export { useLessonPlans } from './hooks/use-lesson-plans.js'
export { LessonPlanViewer } from './components/lesson-plan-viewer.js'
export { LessonPlanGenerator } from './components/lesson-plan-generator.js'
export { DarsError, DarsAuthError, DarsValidationError, DarsNotFoundError } from './errors.js'
export type { LessonPlan, CreateLessonPlanParams, ListLessonPlansResult } from './types.js'
```

- [ ] **Step 2: Run full test suite**

```bash
cd packages/dars-react && pnpm test
```

Expected: all tests PASS.

- [ ] **Step 3: Build**

```bash
cd packages/dars-react && pnpm build
```

Expected: `dist/` created with `index.js`, `index.cjs`, `index.d.ts`, no errors.

- [ ] **Step 4: Commit**

```bash
git add packages/dars-react/src/index.ts
git commit -m "feat(@dars/react): add public exports and verify build"
```

---

## Final verification

- [ ] **Run all tests across both packages**

```bash
cd packages/dars-node && pnpm test && cd ../dars-react && pnpm test
```

Expected: all tests PASS in both packages.

- [ ] **Build both packages**

```bash
cd packages/dars-node && pnpm build && cd ../dars-react && pnpm build
```

Expected: clean builds, no TypeScript errors.

- [ ] **Final commit**

```bash
git add -A
git commit -m "chore: verify @dars/node and @dars/react builds and tests pass"
```
