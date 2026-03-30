# Dars Roadmap

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

## Phase 1.5 — Client-side SDK + React Library
**Status: NOT STARTED**

**Goal:** Publish `@dars/client` and `@dars/react` so FDS teams can embed LP generation in their own UIs without building HTTP clients.

**Scope:**
- `@dars/client` — TypeScript API client wrapping Phase 1 endpoints
- `@dars/react` — React components (LP generator form, LP viewer)
- Handle the 60s wait UX — loading states, polling if needed

**Open questions (revisit when we get here):**
- Do we expose the API key client-side or proxy through FDS team's own backend?
- Synchronous call or do we need async + polling by this point?

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

## Phase 5 — Cross-service Intelligence
**Status: FUTURE / FUZZY**

**Goal:** Integrate signals from other Taleemabad services into LP generation.

**Services to integrate:**
- **Digital Coach** — lecture recordings + feedback → inform LP personalization (e.g., teacher engagement patterns)
- **Exam Generation** — shared infrastructure or result integration
- **Teacher Training** — generated training content informed by LP and curriculum data

*No scope yet. Revisit after Phase 4.*

---

## Parking Lot
Ideas raised but not placed in a phase yet:
- Student-aware LP generation (LP knows class composition)
- Teacher priorities and trends as LP context
- Multi-language support beyond bilingual
- BYOB
- **MCP server** — expose Dars as an MCP server so AI tools (Claude, Cursor, etc.) can generate and retrieve lesson plans natively. Placement TBD.
