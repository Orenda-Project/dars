# Webhooks & Async LP Generation — Design Spec

**Date:** 2026-03-31
**Phase:** 1.2
**Status:** Approved

---

## Goal

Remove the 60s blocking wait from LP generation. Clients queue a job and get notified via webhook when it's done. Polling remains available as a fallback.

---

## Data Model

### `clients` table — new column
```sql
webhook_url VARCHAR(500) NULL
```
Set by admin via `PATCH /api/v1/admin/clients/{id}`. Nullable — clients without a webhook URL still work, they just poll.

### New `webhook_deliveries` table
Tracks every delivery attempt. Foundation for future DLQ.

```sql
CREATE TABLE webhook_deliveries (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id         UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  lesson_plan_id    UUID NOT NULL REFERENCES lesson_plans(id) ON DELETE CASCADE,
  event             VARCHAR(50) NOT NULL,  -- e.g. "lesson_plan.ready"
  payload           JSONB NOT NULL,
  status            VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending | delivered | failed
  attempts          INTEGER NOT NULL DEFAULT 0,
  last_attempt_at   TIMESTAMPTZ NULL,
  next_attempt_at   TIMESTAMPTZ NULL,
  response_status   INTEGER NULL,  -- HTTP status from client's endpoint
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Status values:** `pending` → `delivered` | `failed`

When all 3 retry attempts are exhausted and delivery still fails, `status` is set to `failed`. These records are the DLQ — visible and re-triggerable from the Phase 2.5 dashboard.

---

## Async Flow

### 1. Request (immediate)
`POST /api/v1/lesson-plans` creates the LP row with `status="PENDING"`, enqueues a background task, and returns `202 Accepted` immediately.

### 2. Background task
FastAPI `BackgroundTasks` runs `generate_lesson_plan_task()`:
1. Calls LP assistant via HTTP (~60s)
2. Updates LP to `status="READY"` (with content) or `status="ERROR"`
3. If `client.webhook_url` is set: calls `deliver_webhook()`

### 3. Webhook delivery (`webhooks/service.py`)
1. Creates a `WebhookDelivery` record with `status="pending"`
2. POSTs to `client.webhook_url` with payload (see below)
3. On success (2xx): marks delivery `status="delivered"`
4. On failure: schedules retry as another `BackgroundTask`
   - Attempt 1: immediate
   - Attempt 2: 30s delay
   - Attempt 3: 5min delay
5. After 3 failures: marks delivery `status="failed"` — DLQ record in place

**Known limitation:** Retries are in-process via `BackgroundTasks`. A server restart mid-retry loses the retry. Clients can poll as fallback. Fix path: replace with ARQ/Celery job queue (noted in technical debt).

### Webhook payload
```json
{
  "event": "lesson_plan.ready",
  "lesson_plan": {
    "id": "uuid",
    "client_id": "uuid",
    "status": "READY",
    "grade": "3",
    "subject": "Maths",
    "page_number": "10",
    "content": "<html>...</html>",
    "content_bilingual": null,
    "tags": {},
    "metadata_": {},
    "created_at": "2026-03-31T00:00:00Z",
    "updated_at": "2026-03-31T00:00:00Z"
  }
}
```

Event values: `lesson_plan.ready` | `lesson_plan.error`

No HMAC signing for now — future improvement (noted in technical debt).

---

## API Changes

### `POST /api/v1/lesson-plans`
- **Before:** `201 Created`, blocks ~60s, returns completed LP
- **After:** `202 Accepted`, returns immediately with `status: "PENDING"`, `content: null`
- Response shape unchanged (`LessonPlanResponse`)

### `GET /api/v1/lesson-plans/{id}`
No change. Client polls this to check `status`.

### `GET /api/v1/lesson-plans`
No change.

### `PATCH /api/v1/admin/clients/{client_id}` — new
Admin endpoint to register a webhook URL for a client.

**Request:**
```json
{ "webhook_url": "https://their-server.com/webhooks/dars" }
```

**Response:** `ClientPublicResponse` (existing schema, extended with `webhook_url`)

---

## File Structure

```
server/src/dars/
  webhooks/
    __init__.py
    models.py       — WebhookDelivery SQLAlchemy model
    service.py      — deliver_webhook(), schedule_retry()
  lesson_plans/
    service.py      — refactored: queue_lesson_plan() + generate_lesson_plan_task()
    router.py       — 202 instead of 201
  clients/
    models.py       — add webhook_url column
    schemas.py      — add webhook_url to ClientPublicResponse, new ClientUpdateRequest
    router.py       — add PATCH /api/v1/admin/clients/{id}
    service.py      — add update_client()
supabase/migrations/
  YYYYMMDDHHMMSS_add_webhook_url_to_clients.sql
  YYYYMMDDHHMMSS_add_webhook_deliveries.sql
```

---

## Out of Scope

- HMAC webhook signing (future)
- Dashboard UI for failed deliveries / DLQ (Phase 2.5)
- Persistent job queue (ARQ/Celery) — in-process BackgroundTasks is sufficient for now
- Per-request callback URLs — one URL per client only
