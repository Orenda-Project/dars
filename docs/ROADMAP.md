# Dars Roadmap

## V1 Launch Criteria
Dars v1 is a complete product for internal FDS clients. All of the following must be true before v1 launch:

**Client management:**
- [ ] Admin can register a client and issue an API key
- [ ] Client can authenticate and make API calls

**LP generation:**
- [ ] `POST /api/v1/lesson-plans` — generate an LP asynchronously (no 60s block)
- [ ] `GET /api/v1/lesson-plans/{id}` — retrieve LP + check status
- [ ] `GET /api/v1/lesson-plans` — list LPs with pagination
- [ ] Webhook delivery when LP is ready, with retries

**Integration surfaces:**
- [ ] `@dars/node` published — clients can integrate via Node SDK
- [ ] `@dars/mcp` published — clients' agents can generate LPs via Claude Code / Cursor
- [ ] Dars webapp — clients can log in, generate LPs manually, view history
- [ ] Basic analytics — LP generation count, breakdown by subject/grade, recent activity

**Reliability:**
- [ ] Errors logged and observable (you know when things break)
- [ ] LP generation failures handled gracefully — `ERROR` status returned, webhook fired

**Documentation:**
- [ ] Public API docs (FastAPI OpenAPI) live and accessible
- [ ] `@dars/node` README with quickstart
- [ ] `@dars/mcp` README with config snippet

**Phases required:** 1, 1.2, 1.5, 2.5 (login + LP history + basic analytics)

---

## How to use this document
This is a living document. After completing each phase:
1. Mark it `[DONE]` and note any learnings
2. Re-read the next phase — adjust scope based on what you now know
3. Proceed

Don't over-plan ahead. The value is in the reflection loop, not the upfront detail.

---

## Phase 1 — Thin Proxy: LP Generation via Dars API
**Status: IN PROGRESS**

**Goal:** FDS clients can generate and retrieve lesson plans through Dars using their API key. Dars proxies LP Assistant. Ship something usable fast.

**Scope:**
- `POST /api/v1/lesson-plans` — accepts LP parameters, calls LP assistant synchronously, stores result, returns LP
- `GET /api/v1/lesson-plans` — list LPs for the client
- `GET /api/v1/lesson-plans/{id}` — retrieve a single LP

**Constraints:**
- Synchronous only — no async/webhooks yet
- LP generation takes ~60s — acceptable for now
- No user/teacher/class model yet — LPs belong to the client only

**Out of scope:**
- Edit, complete, delete
- Async / webhook / polling
- React library / client SDK (comes after this works)
- User management

**Done when:** A B2B client can hit Dars, generate an LP, and retrieve it.

---

## Phase 1.2 — Async LP Generation + Webhooks
**Status: NOT STARTED**

**Goal:** Remove the 60s blocking wait from LP generation. Clients queue a job and get notified when it's done.

**Flow:**
1. `POST /api/v1/lesson-plans` → `202 Accepted` immediately with `{ id, status: "PENDING" }`
2. LP generation runs in the background (still proxied to LP assistant via HTTP — will become in-process when Phase 2 lands)
3. Client polls `GET /api/v1/lesson-plans/{id}` for status (fallback)
4. When done, Dars fires a webhook to the client's registered URL with the full LP payload

**Webhook design:**
- One webhook URL per client, registered in account config (not per-request)
- Retry with exponential backoff on delivery failure — 3 attempts: immediate, 30s, 5min
- **Future:** dead-letter queue for failed webhooks — client sees failures in dashboard and can re-trigger manually (revisit in Phase 2.5)

**LP status values:** `PENDING` → `READY` | `ERROR`

**Depends on:** Phase 1 complete.

---

## Phase 1.5 — Integration Layer: Node SDK + MCP Server + React Library
**Status: IN PROGRESS**

**Goal:** Make Dars integration as easy as possible across three surfaces: production Node.js apps, AI agent workflows, and browser UIs.

**Depends on:** Phase 1 complete — all API functionality must be stable before SDK and MCP are published.

### Layer 1 — `@dars/node` (Node.js SDK)
**Status: SCAFFOLDED — needs completion**

TypeScript SDK for server-side Node.js integration. Wraps all Dars API endpoints with typed methods, error classes, and zero boilerplate.

- `dars.lessonPlans.create(params)` — generate an LP
- `dars.lessonPlans.list(options)` — list LPs with pagination
- `dars.lessonPlans.get(id)` — retrieve a single LP
- Typed errors: `DarsAuthError`, `DarsNotFoundError`, `DarsValidationError`
- Express/Next.js middleware (`@dars/node/middleware`) — proxy requests from browser to Dars, injecting the API key server-side so it's never exposed to the client

**Missing:** `DarsClient` entry point class, `index.ts` export, middleware implementation, build config validation.

### Layer 2 — `@dars/mcp` (MCP Server)
**Status: NOT STARTED**

**Depends on:** `@dars/node` complete and published.

An MCP server that wraps `@dars/node` as MCP tools, so AI agents (Claude Code, Cursor, Windsurf) can generate and retrieve lesson plans natively — no HTTP client needed.

**How it works:**
- Lives in `packages/dars-mcp/`
- Thin adapter: translates MCP tool calls → `@dars/node` method calls → Dars API
- Runs as a local subprocess launched by the AI dev tool (stdio transport)
- Client installs once via config block + `DARS_API_KEY` env var:

```json
{
  "mcpServers": {
    "dars": {
      "command": "npx",
      "args": ["@dars/mcp"],
      "env": { "DARS_API_KEY": "sk_xxx" }
    }
  }
}
```

**Tools exposed:**
- `create_lesson_plan` → `dars.lessonPlans.create`
- `get_lesson_plan` → `dars.lessonPlans.get`
- `list_lesson_plans` → `dars.lessonPlans.list`

**Note:** MCP is developer tooling — it runs on the developer's machine inside their AI dev tool. It does not help with production app integration. For that, use `@dars/node` + `@dars/react`.

### Layer 3 — `@dars/react` (React Components)
**Status: SCAFFOLDED — not started**

**Depends on:** `@dars/node` middleware complete.

Drop-in React components for embedding LP generation in browser UIs. The API key stays server-side (proxied via `@dars/node` middleware); the React component talks to the client's own backend.

- `<LPCreationForm />` — form + 60s loading UX + error states
- `<LPRenderer />` — safely renders LP HTML content

**Open questions (revisit when we get here):**
- Synchronous call or async + polling by this point?
- Styling approach — headless/unstyled or opinionated?

---

## Phase 2 — Engine Migration: LP Assistant absorbed into Dars
**Status: NOT STARTED**

**Goal:** Remove the external LP assistant dependency. UG_LessonPlan codebase is copied into `api/src/dars/lp_engine/`. LP generation runs inside the same process.

**Scope:**
- Copy UG_LessonPlan Python code into `dars/lp_engine/`
- Migrate textbook/OCR data from taleemabad-core DB → Supabase
- Remove HTTP call to `lp-assistant.taleemabad.com`
- All FDS units share the same data

**Open questions (revisit when we get here):**
- Does the engine run sync or async within the FastAPI process?
- What exactly needs to be migrated from taleemabad-core's DB? (book content, curriculum definitions, etc.)
- Data freshness: how often does textbook content change?

---

## Phase 2.5 — Web App: Landing Page + Client Analytics Dashboard
**Status: IN PROGRESS — landing page shipped**

**Goal:** Ship a web app (`/webapp`) that gives clients a real UI — login, usage analytics, and account management. Also serves as the public-facing landing page for Dars. This is a high-leverage milestone that makes Dars feel like a product, not just an API.

**Repo layout:** `webapp/` at the repo root. Standalone Next.js 16 app (TypeScript, Tailwind v4, App Router). Not a monorepo package — uses npm with no workspace config. **Do not add a `pnpm-workspace.yaml` or root `package.json`** — this caused a Turbopack module resolution bug that required a full scaffold rebuild. Run `make webapp` to start the dev server.

**Landing page: DONE**
- Public landing page with all sections live (Hero, PlanWindow, Features, How It Works, Quote, CTA, Footer)
- Dars design system: ink/parchment/terracotta palette, Lora serif + Geist Mono, CSS tokens via `@theme` in `globals.css`
- Component architecture: atoms → molecules → templates → page (documented in `webapp/CLAUDE.md`)
- Mobile responsive throughout

**Scope:**
- Public landing page (what is Dars, who it's for, CTA)
- Login with client credentials (maps to existing client API key mechanism — backend may need a session/token auth layer on top)
- Client analytics dashboard:
  - LP generation count over time
  - Breakdown by subject, grade, language
  - Recent LP history
- Super-admin panel (you): create and manage clients, view all usage
- Client self-service (later, within this phase or next): clients manage their own users
- Coverage map: show which regions of Pakistan are supported (by province/board), and which books and languages are available for LP generation
- LP parameter configuration UI: clients set their default LP generation parameters (province/board, grade range, subjects, language, output format preferences) through the web app rather than hardcoding them in API calls — stored per-client, applied automatically on generation

**Depends on:** Phase 1 complete — needs LP data to show analytics against.

**Open questions (revisit when we get here):**
- Session auth: JWT issued by FastAPI, or lean on Supabase Auth?
- Framework: Next.js (SSR, easier auth) vs Vite + React SPA?
- Do clients have sub-users at this point, or is it one login per client?

---

## Phase 2.2 — LP Editing
**Status: NOT STARTED**

**Goal:** Clients can edit generated lesson plans — fix errors, adjust content, add notes — and save the modified version back to Dars.

**Scope (TBD — revisit when Phase 2 is done):**
- `PATCH /api/v1/lesson-plans/{id}` — update LP content
- Edit history / versioning (at minimum: original vs. edited)
- Edited flag on LP so you can distinguish human-modified from raw generated output

**Depends on:** Phase 1 complete, v1 shipped.

---

## Phase 3 — User & Class Model
**Status: NOT STARTED**

**Goal:** FDS users can create classes, assign teachers and students. LP generation can optionally be associated with a teacher/class for tracking and future personalization.

**Key constraint:** LP generation must remain fully usable without any class/teacher/student context. These are additive enrichments.

**Scope (TBD — revisit when Phase 2 is done):**
- Client users (FDS staff identity)
- Teacher records
- Student records
- Class entity (teacher + students, owned by FDS client)
- Associate LP with class/teacher optionally

---

## Phase 3.5 — WhatsApp Product
**Status: NOT STARTED**

**Goal:** Teachers can generate lesson plans by messaging a Dars-operated WhatsApp number. FDS clients share this number with their teachers — no app, no integration, no code required on the client's part.

**This is a product, not a developer tool.** Dars operates the WhatsApp Business number. FDS clients simply onboard their teachers onto it. Everything is backed by the same Dars API so LP history, analytics, and client attribution all work automatically.

**How it works:**
```
Teacher → Dars WhatsApp number → Dars bot → Dars API → LP delivered to teacher
```

**Depends on:**
- Phase 1 — LP generation API stable
- Phase 2.5 — client management exists (teacher is attributed to the right FDS client)
- Phase 3 — teacher records exist in the system (teachers have identities, not just phone numbers)

**Scope (TBD — revisit when Phase 3 is done):**
- Dars operates a WhatsApp Business number via Meta Business API
- Conversational bot: multi-turn dialogue to collect LP params (grade, subject, page number)
- Natural language input — teachers write naturally in Urdu or English, LLM extracts params
- Async flow: immediate acknowledgement → generate → reply when ready (~60s)
- LP delivery: hosted link (`view.dars.taleemabad.com/lp/xyz`) or PDF
- Teacher auth: link WhatsApp number to a teacher record + FDS client
- Usage tracked per client — feeds into Phase 2.5 analytics dashboard

**Note on `@dars/whatsapp` dev tool:** A separate `@dars/whatsapp` package that lets FDS clients build their *own* WhatsApp bots backed by Dars is in the parking lot. This phase is Dars operating the channel directly — that is higher priority.

---

## Phase 4a — LP Quality & Speed
**Status: NOT STARTED**

**Goal:** Improve LP generation quality and reduce the ~60s generation time.

**Ideas (not commitments):**
- Caching, streaming, faster models
- Better prompts, review loops
- Parallel generation for bilingual

*Scope TBD. Revisit after Phase 2 or 3.*

---

## Phase 4b — Curriculum Planning
**Status: NOT STARTED**

**Goal:** Break down a teacher's full academic year into a curriculum plan. Generate LPs with continuity across lessons. Track curriculum coverage.

**Depends on:** Phase 3 (teacher/class model) — curriculum plans belong to a teacher's class.

**Ideas (not commitments):**
- Curriculum breakdown: year → terms → units → lessons
- LP continuity: each LP knows what came before
- Coverage tracking: what has been taught vs. planned
- **Bring-your-own-book (BYOB):** user scans or uploads their own textbook; Dars parses and makes sense of the content (OCR + structure extraction), user picks chapters/topics, Dars generates LPs from that content — unlocks support for books and regions we don't have in our dataset yet

*Scope TBD. Phases 4a and 4b may run in parallel.*

---

## Phase 4c — LP Reviewer
**Status: NOT STARTED**

**Goal:** Automatically review generated lesson plans for quality, completeness, and curriculum alignment. Flag issues before delivery or surface them in the dashboard.

**Scope (TBD — revisit when Phase 4a is done):**
- Bring LP Reviewer logic into Dars (currently lives as a separate service)
- Review runs automatically after generation — results attached to the LP
- Review score + issues visible in the webapp dashboard
- Option to auto-regenerate if review score is below threshold

**Depends on:** Phase 2 (engine in-process — reviewer needs access to generation internals), Phase 4a (quality work — reviewer and quality improvements are tightly related).

---

## Phase 5 — Cross-service Intelligence
**Status: FUTURE / FUZZY**

**Goal:** Integrate signals from other Taleemabad services into LP generation.

**Services to integrate:**
- **Digital Coach** — lecture recordings + feedback → inform LP personalization (e.g., teacher engagement patterns)
- **Exam Generation** — shared infrastructure or result integration
- **Teacher Training** — generated training content informed by LP and curriculum data

*No scope yet. Revisit after Phase 4.*

---

## Technical Debt & Future Improvements
Known shortcuts taken intentionally. Revisit when the pain is felt.

### Async / Background Jobs
- **Retry durability** — webhook retries are scheduled via FastAPI `BackgroundTasks` (in-process). If the server restarts mid-retry, the retry is lost. Clients can poll as fallback. Fix: replace with a proper job queue (ARQ or Celery) when reliability becomes a requirement.
- **Job queue** — LP generation itself runs as a `BackgroundTask`. Under high load this will saturate the server. Fix: move to ARQ/Celery with a dedicated worker process.
- **Webhook DLQ** — `WebhookDelivery` table with `status="failed"` is the foundation. Fix: expose failed deliveries in the Phase 2.5 dashboard with a manual re-trigger button.

### SDK
- **`@dars/node` missing entry point** — `DarsClient` class and `index.ts` not yet written. Package is scaffolded but not usable.

### Infrastructure
- **No staging environment** — only `dars-dev` Supabase project exists. `dars-prod` not yet created. Risk: dev and prod share the same DB if not separated before launch.

---

## Parking Lot
Ideas raised but not placed in a phase yet:
- Student-aware LP generation (LP knows class composition)
- Teacher priorities and trends as LP context
- Multi-language support beyond bilingual
- BYOB
- **`@dars/whatsapp` dev tool** — a package FDS clients use to build their *own* WhatsApp bots backed by Dars. Lower priority than the Dars-operated WhatsApp product (Phase 3.5) — revisit after that ships.
- LP editing AI assist — AI-powered suggestions while editing an LP (e.g. "improve this activity section")

