# Dars — Deep Critique & Analysis
*Written 2026-03-31. Personal, candid, thorough.*

---

## The Short Version

Dars is a well-conceived, cleanly architected service that is about 60% done on Phase 1, despite the roadmap saying "IN PROGRESS." The foundation is excellent — the decisions made early (FastAPI, row-level isolation, SHA-256 API keys, no Celery) are all correct. The documentation culture is exceptional for a project this size. But there are real structural problems — a 60-second blocking HTTP call that is the whole point of the product, an SDK layer that exists mostly as scaffolding, and a roadmap that is simultaneously too ambitious and not ambitious enough in the right places.

This document covers: what's working, what's broken, what's missing, architectural concerns, product advice, and suggested feature work — roughly in order of importance.

---

## What's Working Well

### Architecture decisions are sound

Every key ADR holds up to scrutiny:

- **FastAPI over Django REST** — correct for an async-native proxy service. Django's ORM is synchronous at its core; fighting that would have been painful. FastAPI's auto-OpenAPI also generates the Bruno collection automatically, which is a real quality-of-life win.

- **Row-level multi-tenancy** — for an internal B2B service with ~10 clients, schema-per-tenant would have been massive overkill. Single schema + `client_id` FK is correct. The enforcement pattern (`get_current_client` dependency → injected everywhere) is exactly right.

- **No Celery** — correct for now. BackgroundTasks is sufficient. Celery would add Redis, worker processes, deployment complexity — all for a handful of internal clients. The call to graduate to async is right, but the solution doesn't need to be Celery (see below).

- **SHA-256 API keys** — correct. No session state, timing-attack-safe comparison via `hmac.compare_digest`, shown once and never stored. Clean.

- **Supabase** — correct for this scale. Managed Postgres, built-in migrations CLI, dashboard for inspection, free tier. The right tradeoff.

### Code organization is clean

The `models.py / schemas.py / service.py / router.py` pattern per feature module is textbook FastAPI organization. The separation is meaningful: models own DB shape, schemas own API shape, service owns logic, router owns routing. No logic leaks into routers. Service functions are testable in isolation. This is good discipline.

### Testing philosophy is right

Using SQLite in-memory for unit tests is the right call. Supabase integration tests would be slow, fragile, and require network access. The mock strategy (mock `_call_lp_assistant`, mock `get_client_by_api_key`) isolates what needs isolating. Cross-client isolation is tested explicitly (`test_get_lesson_plan_cross_client_isolation`) — this is the kind of test most projects skip and regret.

### Documentation is genuinely excellent

The ADRs exist and are readable. The roadmap is opinionated and honest. The CLAUDE.md is dense with real gotchas (`sqlalchemy.types.Uuid` vs PG dialect, `hmac.compare_digest`, settings singleton). The context docs about Taleemabad's internal services are written for the next person, not for the current author. This is unusual and valuable.

### Landing page is polished

The webapp landing page is well done — the ink/parchment/terracotta design system is coherent and distinctive, the atom → molecule → template → page architecture scales correctly, and the mobile-responsive work is thorough. The PlanWindow browser-chrome mockup is a good product communication device.

---

## What's Broken (or Will Break Soon)

### The generation call is synchronous and 60 seconds long

This is the most pressing issue in the codebase and it's not fixed.

```python
async with httpx.AsyncClient(timeout=300.0) as http:
    response = await http.post(
        f"{settings.lp_assistant_url}/api/generate-lp",
        ...
    )
```

**Why this is dangerous:** FastAPI is async, but that doesn't mean it handles 300-second connections gracefully. Each open connection holds a database session (`AsyncSession` is acquired per-request), a TCP connection to LP Assistant, and an event loop slot. Under load — even modest load with 5 clients each generating a few LPs — this will saturate the Postgres connection pool long before the LP generation itself becomes a bottleneck. Supabase's free tier connection limit is 60; every hanging generation ties up one.

**The fix for now (Phase 1.2, already in roadmap):** Move generation off the request/response cycle. `POST /api/v1/lesson-plans` should return `202 Accepted` with `{ id, status: "PENDING" }` immediately and kick off generation as a background task. The service can still proxy to LP Assistant — just not on the same connection.

**What to actually use for background tasks:** FastAPI's `BackgroundTasks` has a problem here: it runs in the same process, on the same event loop, and there's no visibility into running tasks, no retry on crash, and if the server restarts mid-generation the task is silently dropped. For production, use a task queue. For this project's scale, `arq` (async Redis queue, tiny footprint) or just a Postgres-backed queue via `pgqueuer` is the right move — no Celery, no additional infra beyond what Supabase already provides.

### Error handling in generation is too broad

```python
except Exception as e:
    logger.error("LP assistant failed for lp_id=%s: %s", lp.id, e)
    lp.status = "ERROR"
```

This catches everything — including database errors, network errors, JSON decode errors, timeout errors, 4xx errors from LP Assistant, 5xx errors from LP Assistant. The LP record gets marked `ERROR` without distinguishing between:

- LP Assistant returned a 422 (bad params — caller's fault, retry won't help)
- LP Assistant returned a 503 (overloaded — retry will help)
- Network timeout (may be transient)
- JSON decode error (LP Assistant returned garbage)

For the client using the API, `status: "ERROR"` with no further detail is frustrating. They don't know whether to retry, fix their input, or call someone. The `metadata_` field exists — use it: store `{ "error": { "type": "timeout", "http_status": null, "message": "LP assistant did not respond within 300s" } }`. Then expose that in `LessonPlanResponse`.

### `@dars/node` is a scaffold, not an SDK

The package exists. `types.ts` is solid. `errors.ts` is solid. `lesson-plans.ts` has the resource class with method signatures. But:

- There is no `DarsClient` class — the entry point that users actually import
- There is no `index.ts` — nothing is exported from the package
- Middleware (`createDarsHandler`) doesn't exist
- The package cannot be built and used

This is blocking Phase 1.5 entirely. If a client wanted to integrate today, they'd have to write raw `fetch()` calls. The SDK should be the first deliverable after Phase 1 is truly complete.

### `@dars/react` doesn't exist

It's a folder with a `package.json`. The most valuable thing it could contain — `<LPCreationForm />` with a built-in 60-second loading state + `<LPRenderer />` with sanitized HTML rendering — isn't started. For FDS teams building browser tools, this is the thing that saves them hours of integration work.

### No retry or resilience on LP Assistant calls

If LP Assistant returns a 503, generation fails permanently for that LP record (status: `ERROR`). There's no retry. The client has to create a new LP from scratch. Given that LP Assistant is an external service run by a different team, transient failures are expected. A simple exponential backoff retry (3 attempts, 2s/10s/60s) in `_call_lp_assistant` would prevent most user-facing errors.

---

## Architectural Concerns

### The `metadata_` field naming is a smell

```python
metadata_: dict[str, Any]  # in schemas
metadata_ = Column(JSONB)   # in models
```

The trailing underscore exists because `metadata` is a reserved name in SQLAlchemy. This bleeds into the API response — clients get `metadata_` in the JSON, which is odd. The solution: use `model_serializer` or `Field(alias="metadata")` in Pydantic to serialize it as `"metadata"` in the API output while keeping the Python attribute name `metadata_`. The OpenAPI spec should show `metadata`, not `metadata_`.

### Pagination is cursor-less

```python
GET /api/v1/lesson-plans?limit=20&offset=100
```

Offset pagination has a classic problem: if new records are inserted between page 1 and page 2 requests, the client gets duplicates or misses records. For a list of lesson plans sorted by `created_at desc`, this matters — generation is ongoing and new LPs appear frequently. Cursor-based pagination (`?after=<created_at_timestamp>&limit=20`) is more correct. This is a breaking API change if delayed — fix it before Phase 1 is called complete and external clients are depending on the offset behavior.

### No `updated_at` handling in schemas

`LessonPlanResponse` includes `updated_at`, which is good. But `LessonPlanCreateRequest` doesn't expose `topic` persistence correctly — `topic` is stored but if the LP Assistant infers a topic from the page number and returns it in `tags.topic`, that's stored in `tags`, not in `topic`. The `topic` field on the model is the user-supplied override. After generation, clients may want to see the resolved topic. Consider promoting `tags.topic` → `lp.topic` during the generation update step.

### No API versioning enforcement

The routes are versioned (`/api/v1/...`) which is correct. But there's no version negotiation, no deprecation header, no changelog for the API contract. Right now this doesn't matter — there's one version. But Phase 1.2 changes the response shape of `POST /api/v1/lesson-plans` (from a full LP to `202 Accepted` with partial data). That's a breaking change. It should be communicated explicitly in the roadmap and client docs before it ships.

### Supabase connection handling under async load

SQLAlchemy async sessions + asyncpg + Supabase has a subtle issue: the default connection pool size in SQLAlchemy is 5. Under concurrent generation (even 3 simultaneous LP requests), the pool can saturate and requests will queue waiting for a connection while also holding... a connection to LP Assistant. This creates a deadlock-adjacent situation. Set `pool_size=10, max_overflow=20` in the engine config and monitor pool wait time.

---

## What's Missing From Phase 1 (that should block Phase 2)

These aren't future features — they're gaps in what Phase 1 was supposed to deliver:

### 1. LP deletion endpoint

The roadmap says "edit, complete, delete" are out of scope for Phase 1. Fair. But delete is table stakes for any data API. FDS users who generate LPs with wrong params (wrong grade, wrong page) have no way to remove them. They accumulate indefinitely. Add `DELETE /api/v1/lesson-plans/{id}` (soft-delete via `status = "DELETED"` or hard delete — hard delete is fine at this scale).

### 2. Webhook URL per client

Phase 1.2 plans webhook delivery but requires a registered URL per client. That URL needs to be stored somewhere — an `accounts` table or just a `webhook_url` column on `clients`. This schema migration should happen before Phase 1.2 starts, not as part of it. Schema migrations on an active DB are more dangerous than schema design.

### 3. Client deactivation

There's `is_active: bool` on the `Client` model but no endpoint to set it to `False`. The admin endpoint `POST /admin/clients` creates clients. There's no `PATCH /admin/clients/{id}` to deactivate them, rotate their key, or update their name. If a client's key is compromised, there's no way to disable access without directly editing the database.

### 4. Rate limiting

There is none. A client (or a bug in a client's code) could hit `POST /api/v1/lesson-plans` in a loop and exhaust LP Assistant's capacity for everyone. Even a simple per-client rate limit (10 concurrent generations, 100/day) via Redis or Postgres-backed token bucket would prevent abuse. At minimum, limit concurrent in-flight generations per client.

---

## Product Observations

### The naming is good, but the branding needs a story

"Dars" (درس) is a good name — short, meaningful, bilingual. The landing page's design system (ink/parchment/terracotta) communicates "education" without being childish. But the landing page's copy doesn't make clear who the audience is. "Build the lesson plan layer" is an engineering headline. FDS teams are field specialists, not engineers. If the web app will eventually serve FDS teams directly (Phase 2.5 dashboard), the copy needs two registers: one for the engineers integrating the API, one for FDS teams using the dashboard.

### The MCP server is the sleeper feature

`@dars/mcp` is listed in the parking lot and Phase 1.5. It's actually one of the most strategically valuable pieces of the roadmap. An MCP server means FDS specialists using Claude Code (or Claude generally) can generate lesson plans via natural language — no web app, no API calls, no code. This is zero-friction access for non-technical users. It also creates an extremely short feedback loop for testing: open Claude Code, generate an LP, see the result. That's faster than any web UI.

The dependency chain (Phase 1 → @dars/node → @dars/mcp) is correct. But the MCP server should be prioritized above `@dars/react` once `@dars/node` exists. React components help developers build UIs; MCP helps everyone use the product immediately.

### WhatsApp product (Phase 3.5) is the highest-leverage item on the roadmap

Everything before Phase 3.5 is infrastructure for developers. Phase 3.5 is the first time an actual teacher gets access without needing an FDS team member to manually run a generation. That's a step-function change in reach. The 60-second latency (currently blocking) is actually fine for WhatsApp — users expect to wait for a "sending..." message. Async generation + WhatsApp delivery is a natural fit.

The dependency on Phase 3 (teacher records) is worth questioning. A minimal WhatsApp product could work with just Phase 1 — identify teachers by their phone number, attribute to a client by how they discovered the WhatsApp number (referral code), generate LP, reply. Teacher records add attribution and history but aren't strictly required for a first version.

### Curriculum coverage map is an underrated feature

The roadmap mentions a "coverage map: show which regions of Pakistan are supported." This is actually a killer feature for FDS teams — before they deploy Dars to a region, they need to know whether the textbooks for that province/board are in the dataset. A visual coverage map (province → board → subjects → grades → available?) turns a question they currently answer by asking the LP Assistant team into a self-service feature. Build it early in Phase 2.5.

### Phase 4b's BYOB is the right long-term moat

Bring-Your-Own-Book (upload textbook → OCR → extract structure → generate LPs) is the feature that makes Dars independent of Taleemabad's internal textbook dataset. Right now, Dars can only generate LPs for books in LP Assistant's database. BYOB removes that constraint and makes Dars useful to any school system, not just ones whose books Taleemabad has digitized. This is where the product crosses from internal tool to standalone product.

---

## Specific Technical Improvements

### 1. Add `topic` resolution after generation

```python
# After successful LP Assistant call:
resolved_topic = result.get("tags", {}).get("topic")
lp.topic = lp.topic or resolved_topic  # user override takes precedence
lp.tags = result.get("tags") or {}
```

### 2. Serialize `metadata_` as `metadata` in API output

```python
class LessonPlanResponse(BaseModel):
    metadata_: dict[str, Any] = Field(alias="metadata")

    model_config = {"from_attributes": True, "populate_by_name": True}
```

### 3. Add structured error info to LP records

```python
# In the error handler:
lp.metadata_ = {
    "error": {
        "type": type(e).__name__,
        "message": str(e),
        "http_status": e.response.status_code if hasattr(e, 'response') else None,
    }
}
lp.status = "ERROR"
```

### 4. Switch to cursor pagination

```python
GET /api/v1/lesson-plans?limit=20&before=2026-03-30T12:00:00Z
# Returns: { items, next_cursor, has_more }
```

### 5. Add `X-Request-ID` header propagation

Every request should get a correlation ID that propagates into LP Assistant calls and into log lines. Right now debugging a failed generation means grepping logs by `lp_id` — which only works if you already know the LP ID. A request ID logged from the moment the HTTP request arrives makes distributed tracing possible later.

### 6. Add `curriculum` to `LessonPlanResponse`

```python
# Currently missing from the response schema:
curriculum: str
```

Clients want to see the curriculum used for generation. It's stored on the request but not on the model or response. Add it to both.

### 7. Validate grade and subject against known values

Right now `grade` and `subject` are free strings. A client sending `grade: "Grade 3"` vs `grade: "3"` vs `grade: "three"` will get different behavior depending on what LP Assistant does with it. Dars should normalize inputs (or at least validate them against a known set) before passing to LP Assistant. A Pydantic validator on `LessonPlanCreateRequest` that canonicalizes `grade` would catch the most common mistakes at the API boundary.

---

## CI/CD and DevOps Gaps (non-trivial)

The project has no:

- **GitHub Actions** — no automated tests on PR, no linting gate, no build validation for the SDK packages
- **Sentry or equivalent** — no error tracking in production; you only know about failures if you read logs manually
- **Structured logging** — `colorlog` is great for development but JSON-formatted logs are needed for any log aggregation system (Datadog, Papertrail, Supabase's built-in logging)
- **Health check depth** — `/health` returns `{ status: "ok" }` but doesn't check DB connectivity or LP Assistant reachability. A real health check would query `SELECT 1` against the DB and return component-level status.
- **Environment promotion** — `dars-dev` → `dars-prod` migration path is not defined. Supabase CLI makes this manageable but the process needs to be documented before it's needed.

---

## What I Would Do Differently

### Architecture

1. **Background task queue from day one** — even a simple Postgres-backed queue (one table, one worker) would have made Phase 1.2 a 2-hour addition instead of a phase. The sync generation design is a dead end that needs to be ripped out.

2. **LP Assistant as an internal dependency, not an external service** — the 5-phase roadmap treats LP absorption (Phase 2) as far-future. If LP Assistant is a Python service in the same organization, copying it into `dars/lp_engine/` is weeks of work, not months. Doing it earlier would remove the biggest reliability risk (external HTTP call in the critical path) and improve generation speed.

3. **Webhook URL on client from day one** — the `clients` table should have had `webhook_url`, `webhook_secret`, and `config` (JSONB for LP defaults) from the first migration. Adding these later means migrations on a live table with data.

### Product

1. **Ship the MCP server before the React components** — it's faster to build, requires less infrastructure (no middleware proxy layer), and gives you a dogfood path for testing the API with real use cases.

2. **LP parameter defaults per client** — FDS clients almost always use the same curriculum, grade range, and subjects for their region. Storing defaults per client (in a `config` JSONB column) means they don't have to send the same params on every request. This is a small feature with outsized DX improvement.

3. **LP preview endpoint** — `GET /api/v1/lesson-plans/{id}/preview` returns the HTML with no auth required but with a signed token (short-lived). Lets FDS teams share LP outputs with teachers or stakeholders without exposing the API or building a viewer UI. Pairs well with the WhatsApp product (deliver a preview link instead of raw HTML).

---

## Summary Scorecard

| Area | Grade | Notes |
|------|-------|-------|
| API design | B+ | Clean, versioned, correct auth. Missing delete, rate limits, cursor pagination. |
| Data model | A- | Solid schema. `curriculum` not stored, `metadata_` naming is a wart. |
| Business logic | B | Generation flow correct but synchronous and fragile. Error handling too broad. |
| Testing | B+ | Good coverage of critical paths. Missing integration tests, frontend tests. |
| SDK (node) | D | Scaffolded but unusable. Blocking Phase 1.5. |
| SDK (react) | F | Doesn't exist yet. |
| Webapp | B+ | Landing page excellent. Auth/dashboard not started. |
| Documentation | A | Genuinely exceptional for a project this size. |
| DevOps | D | No CI, no monitoring, no structured logging, no prod environment. |
| Product vision | A | Roadmap is ambitious and well-reasoned. WhatsApp + BYOB are strong bets. |

**Overall: B.** The foundation is excellent. The pressing work is: finish Phase 1 properly (delete endpoint, client management, async generation), then complete `@dars/node`, then build the MCP server. That sequence unlocks everything else.

---

*End of critique. This document should be revisited and updated after Phase 1.2 ships.*
