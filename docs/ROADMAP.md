---
type: reference
last_verified: 2026-04-08
owner: hataf
---

# Dars — Roadmap

Ordered roughly by priority. No phases — just work. Move things up or down as priorities shift. Open a bead when you start something.

---

## Up next

- **`@dars/node` SDK** — `DarsClient` entry point class, `index.ts` export, middleware (proxy requests from browser, inject API key server-side), build config, publish to npm
- **Webhook DLQ UI** — expose failed webhook deliveries in the dashboard with a manual re-trigger button (`WebhookDelivery` table with `status="failed"` already exists)
- **LP generation error handling** — graceful `ERROR` status returned to client, webhook fired on failure (currently errors may not fire webhooks)
- **Observability** — errors logged and surfaced somewhere you can see when things break

---

## Soon

- **Client analytics dashboard** — LP generation count over time, breakdown by subject/grade/language, recent LP history
- **Client login** — session auth for the webapp (JWT from FastAPI or Supabase Auth)
- **`@dars/mcp` server** — wraps `@dars/node` as MCP tools so AI agents can generate LPs natively; depends on `@dars/node` being published
- **`@dars/react` components** — `<LPCreationForm />` and `<LPRenderer />`; depends on `@dars/node` middleware
- **Store `curriculum` on LP** — currently hardcoded to `"ICT"` in edit flow; should be persisted at creation time

---

## Later

- **Engine migration** — copy `UG_LessonPlan` into `dars/lp_engine/`, migrate textbook/OCR data to Supabase, remove HTTP dependency on `lp-assistant.taleemabad.com`
- **LP editing UI** — edit history view (diff original vs. edited), manual edit in webapp
- **Super-admin panel** — create and manage clients, view all usage
- **Coverage map** — which regions, books, and languages are supported
- **LP parameter config UI** — clients set default LP params (province/board, grade range, subjects, language) in webapp instead of hardcoding in API calls
- **Staging environment** — separate `dars-prod` Supabase project; currently only `dars-dev` exists
- **Job queue** — replace `BackgroundTasks` with ARQ/Celery for retry durability and load handling
- **WhatsApp product** — teachers generate LPs by messaging a Dars-operated WhatsApp number; depends on client management + teacher records
- **User and class model** — FDS users, teacher records, student records, class entity; LP generation stays usable without it

---

## Parking lot

Ideas raised, not yet prioritized:

- `@dars/react` async + polling UX (depends on whether async LP is the norm by then)
- LP reviewer integration — auto-review after generation, score + issues in dashboard
- LP editing AI assist — AI suggestions while editing (e.g. "improve this activity")
- Student-aware LP generation
- Teacher priorities and trends as LP context
- Multi-language support beyond bilingual
- Bring-your-own-book (BYOB) — upload textbook, generate LPs from it
- `@dars/whatsapp` dev tool — for FDS clients building their own WhatsApp bots backed by Dars
- Cross-service intelligence (Digital Coach, Exam Generation, Teacher Training)
- Curriculum planning — year → terms → units → lessons with continuity
