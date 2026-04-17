---
type: reference
last_verified: 2026-04-17
owner: hataf
---

# Dars — Roadmap

Ordered roughly by priority. Open a bead when you start something.

---

## Phase 1 goal: curriculum-driven LP generation

The end state: a client picks a curriculum (book + grade + subject + SLO provider), the system breaks each topic into a plan of lesson plans, and generates them. Teachers get a full term's worth of LPs, each grounded in the textbook topic and the correct sub-SLOs.

Full spec: [docs/specs/curriculum-lp-breakdown.md](specs/curriculum-lp-breakdown.md)

### What needs to be built

**1. Data layer (migrations in progress)**
- Sub-SLOs — schema + import from Schema tool
- Topics — model under `book_chapters`
- `topic_sub_slos` — join table linking topics to sub-SLOs
- Curriculums — named plan per book/grade/subject/provider/year
- Curriculum topics — ordered topic list within a curriculum
- LP stubs — one row per LP-to-be-generated, output of the breakdown module

**2. LP Breakdown Module**
AI step: given a curriculum topic (title, text, sub-SLOs, grade, subject), output a sequence of LP stubs: `(skill_type, cpa_phase, blooms_level)`. This decides how many LPs a topic needs and what kind — e.g. 2 reading, 1 comprehension, 1 revision.

**3. LP Assistant: topic-text mode**
Currently LP Assistant takes `page_number` and fetches OCR text internally. We need it to also accept `topic_text` + `sub_slos` + `skill_type` + `cpa_phase` + `blooms_level` directly. This is a change in `UG_LessonPlan/`. Without it, Dars cannot generate LPs from curriculum topics.

**4. Stub generation**
Trigger LP generation per stub (async, same pattern as existing LP generation). On success: stub `status → generated`, `lesson_plan_id` set.

---

## Up next (platform work)

- **`@dars/node` SDK** — `DarsClient` entry point, middleware, publish to npm
- **Webhook DLQ UI** — expose failed deliveries in dashboard, manual re-trigger
- **LP generation error handling** — graceful `ERROR` status + webhook on failure
- **Observability** — errors logged and surfaced

---

## Soon

- **Client accounts** — self-serve signup; `Client` gets `email`, `password_hash`, `config` (default curriculum, grade, subject, language); session token for webapp login
- **Client analytics dashboard** — LP count over time, breakdown by subject/grade/language
- **EG integration — Phase 1** — exam generation as standalone feature: `POST /exam-generations` (async), webhook from `UG_EG`, webapp UI. Mirrors LP async flow.

---

## Later

- **EG integration — Phase 2** — generate exam from an existing LP; LP detail shows associated exams
- **Engine migration** — copy `UG_LessonPlan` into `dars/lp_engine/`, remove HTTP dependency on `lp-assistant.taleemabad.com`
- **LP editing UI** — edit history view (diff original vs. edited), manual edit in webapp
- **Super-admin panel** — create and manage clients, view all usage
- **Staging environment** — separate `dars-prod` Supabase project
- **Job queue** — replace `BackgroundTasks` with ARQ/Celery for retry durability
- **WhatsApp product** — teachers generate LPs via Dars-operated WhatsApp number

---

## Parking lot

- LP reviewer integration — auto-review after generation, score + issues in dashboard
- LP editing AI assist — AI suggestions while editing
- Continuity across LPs — carry forward context from LP n to LP n+1 within a topic
- `@dars/react` components — `<LPCreationForm />`, `<LPRenderer />`
- `@dars/mcp` server — MCP tools wrapping `@dars/node`
- Coverage map — which boards, books, grades are supported
- Multi-language support beyond bilingual
- Student-aware LP generation
- Cross-service intelligence (Digital Coach, Exam Generation, Teacher Training)
