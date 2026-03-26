# Dars — Initial Design Spec

**Date:** 2026-03-26
**Status:** Approved

---

## What Is Dars?

Dars is an independent B2B service that provides lesson plan (LP) creation and rendering infrastructure for internal Taleemabad teams. Teams building apps for specific regions of Pakistan (Punjab, Sindh, etc.) can integrate LP functionality by installing an npm package and pointing it at the Dars API — without forking or depending on taleemabad-core.

The name **Dars** (درس) means "lesson" in Urdu.

---

## Problem

Taleemabad's LP system lives inside a Django monolith (`taleemabad-core`). Internal teams that want LP functionality today have two bad options:

1. Duplicate the logic in their own apps
2. Depend on the monolith directly (tight coupling, no clear API contract)

Dars solves this by extracting LP functionality into a standalone service with a documented API and reusable frontend components.

---

## Goals (This Phase)

1. **REST API** — FastAPI service with full LP lifecycle (generate, view, edit, complete)
2. **Client SDK** — `@dars/client` TypeScript package for typed API access
3. **React SDK** — `@dars/react` npm package with `<LPCreationForm />` and `<LPRenderer />`
4. **B2B auth** — API key per client team, row-level data isolation
5. **Documentation** — Auto-generated OpenAPI at `/docs`, ADRs for key decisions

---

## Out of Scope (This Phase)

- Internalizing LP Assistant AI logic (currently delegated to external microservice)
- External/pre-built lesson plans (book-mapped)
- Offline caching (clients handle in their apps)
- Mobile SDK
- Billing or rate limiting per client

---

## Architecture

```
Consumer App (Punjab team, Sindh team, etc.)
       │
       │  X-API-Key header
       ▼
┌─────────────────────────────┐
│         Dars API            │  FastAPI, Python 3.12
│                             │
│  /api/v1/lesson-plans/*     │
│  /internal/clients          │
│                             │
│  BackgroundTasks (async)    │──────► LP Assistant microservice
└────────────┬────────────────┘        (lp-assistant.taleemabad.com)
             │
             │ SQLAlchemy async (asyncpg)
             ▼
      Supabase PostgreSQL
      (hosted, row-level isolation via client_id)
```

Consumer apps also optionally install:
- `@dars/client` — typed TypeScript API client
- `@dars/react` — React components (LPCreationForm, LPRenderer)

---

## Data Models

### Client (tenant)
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| name | str | e.g. "Punjab Team" |
| api_key_hash | str | SHA-256 of raw key, never stored plain |
| is_active | bool | soft disable |
| created_at | datetime | |

### LessonPlan
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| client_id | UUID | FK → Client (row isolation) |
| external_ref | str? | Client's own ID for cross-referencing |
| grade | str | e.g. "G3" |
| subject | str | e.g. "Math" |
| topic | str? | |
| page_number | int? | |
| class_strength | int? | |
| content | text | HTML |
| content_bilingual | text? | HTML in Urdu |
| status | enum | PENDING \| READY \| ERROR |
| metadata | JSONB | tokens, cost, generation time |
| tags | JSONB | arbitrary client-defined tags |
| created_at | datetime | |
| updated_at | datetime | |

### LessonPlanEdit
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | PK |
| lesson_plan_id | UUID | FK → LessonPlan |
| content | text | HTML snapshot |
| edit_source | enum | USER \| AI \| GENERATED |
| edit_instruction | str? | instruction given for AI edit |
| metadata | JSONB | |
| created_at | datetime | |

---

## API Endpoints

### Public (requires `X-API-Key` header)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/lesson-plans/generate` | Create LP + queue AI generation |
| GET | `/api/v1/lesson-plans` | List all LPs for this client |
| GET | `/api/v1/lesson-plans/{id}` | Get single LP |
| PATCH | `/api/v1/lesson-plans/{id}` | Update LP content (user edit) |
| POST | `/api/v1/lesson-plans/{id}/ai-edit` | Request AI edit (max 3 per LP) |
| POST | `/api/v1/lesson-plans/{id}/complete` | Mark complete + rating/feedback |
| GET | `/api/v1/lesson-plans/{id}/edits` | Get edit history |

### Internal (no auth, localhost only or internal network)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/internal/clients` | Create client + return raw API key (shown once) |

---

## Auth

- Every public request must include `X-API-Key: <raw_key>`
- On each request: hash the raw key → look up Client by hash → inject client into request state
- All DB queries automatically filter by `client_id` — no cross-client data leakage possible
- Raw API key shown exactly once on client creation; only the hash is stored

---

## Multi-Tenancy

Row-level isolation via `client_id` foreign key on all data tables. No schema-per-tenant complexity. All clients share one Supabase project and one schema.

---

## Frontend Packages

### `@dars/client`
Typed TypeScript fetch wrapper. Auto-infers types from API schemas.

```ts
const dars = new DarsClient({ apiKey: 'dars_...', baseUrl: 'https://api.dars.taleemabad.com' })
const lp = await dars.lessonPlans.generate({ grade: 'G3', subject: 'Math', topic: 'Fractions' })
```

### `@dars/react`
Two React components, zero opinions about styling.

**`<LPCreationForm />`** — handles the generate call + polling until READY
**`<LPRenderer />`** — renders LP HTML content, optional bilingual toggle, optional edit mode

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API language | Python 3.12 |
| API framework | FastAPI |
| DB ORM | SQLAlchemy 2.x async |
| DB driver | asyncpg |
| DB host | Supabase (PostgreSQL 15) |
| Migrations | Supabase CLI (`supabase/migrations/`) |
| Settings | pydantic-settings |
| Background tasks | FastAPI BackgroundTasks |
| API containerization | Docker + docker-compose |
| Frontend packages | React 18, TypeScript 5, Vite (library mode) |
| Package manager (JS) | pnpm |
| Testing (Python) | pytest + pytest-asyncio + httpx |

---

## Decisions Log

See `docs/adr/` for full Architecture Decision Records.

- **ADR-001:** FastAPI over Django REST — async-native, lighter, better OpenAPI generation
- **ADR-002:** Row-level multi-tenancy — simpler ops than schema-per-tenant; sufficient for internal B2B
- **ADR-003:** Supabase for database — hosted Postgres, no local DB container needed, dashboard for inspection
- **ADR-004:** API keys over JWT — stateless, simple, sufficient for service-to-service B2B auth
- **ADR-005:** Delegate to LP Assistant — reuse proven AI logic; internalize in a future phase
