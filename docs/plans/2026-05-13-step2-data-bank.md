---
type: plan
last_verified: 2026-05-13
owner: hataf
---

# Plan: Step 2 — Data Bank (Books + SLOs per Curriculum)

## What this does

Books and SLOs are tied to curricula (NCP or SNC) instead of the old "ICT"/"Punjab" strings. Adds an SLO table and topic-SLO mapping. Client access to books and SLOs is automatically scoped to their curriculum. Admin can import SLOs in bulk and map them to topics.

## Why

The data bank is the foundation of content — it defines what books exist, what topics they contain, and what learning outcomes each topic covers. Everything downstream (chapter planning, LP generation, assessment generation) depends on this being correctly attributed to a curriculum.

## What changes

### DB

Migration: `server/src/dars/migrations/20260513000004_slos.sql`

Note: `books.curriculum` already FKs to `curriculums(code)` via `init_clean.sql`. The data migration (ICT→NCP, Punjab→SNC) only applies to any legacy rows from old deployments — staging DB is clean so it's a no-op but kept for safety.

```sql
-- Data: map any legacy book curriculum values to new codes
UPDATE books SET curriculum = 'NCP' WHERE curriculum = 'ICT';
UPDATE books SET curriculum = 'SNC' WHERE curriculum IN ('Punjab', 'Sindh');

-- SLOs table
CREATE TABLE IF NOT EXISTS slos (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  curriculum      TEXT NOT NULL REFERENCES curriculums(code),
  grade           INT NOT NULL,
  subject         TEXT NOT NULL,
  code            TEXT NOT NULL,      -- e.g. "R1.1", "M3.2"
  description     TEXT NOT NULL,      -- the learning outcome text
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (curriculum, code)
);

-- Topic-SLO mapping
CREATE TABLE IF NOT EXISTS topic_slos (
  topic_id  UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
  slo_id    UUID NOT NULL REFERENCES slos(id) ON DELETE CASCADE,
  PRIMARY KEY (topic_id, slo_id)
);
```

### Backend — update `curriculum/` module

`models.py`:
- `Book.curriculum` — FK already points to `curriculum` text column; constraint updated in migration
- Add `SLO` model (table: `slos`)
- Add `TopicSLO` model (table: `topic_slos`)

`router.py` — update existing endpoints:
- `GET /api/v1/books` — remove `curriculum?` query param; filter automatically by `client.curriculum`
- `GET /api/v1/books/{id}/chapters/{chapter_id}/topics` — unchanged

New endpoints (client-facing):
- `GET /api/v1/slos` — list SLOs for client's curriculum (filter: `grade?`, `subject?`)
- `GET /api/v1/topics/{id}/slos` — SLOs mapped to a specific topic

New endpoints (admin):
- `POST /admin/slos/import` — bulk import SLOs for a curriculum
  - Body: `{curriculum: "NCP", slos: [{grade, subject, code, description}]}`
  - Upserts by `(curriculum, code)`
- `POST /admin/topics/{id}/slos` — map SLO codes to a topic
  - Body: `{slo_codes: ["R1.1", "R1.2"]}`
  - Upserts into `topic_slos`
- `DELETE /admin/topics/{id}/slos` — clear all SLO mappings for a topic

`schemas.py` — add:
- `SLORead`: id, curriculum, grade, subject, code, description
- `SLOListResponse`: items, total
- `SLOImportRequest`: curriculum, slos (list)
- `TopicSLOsResponse`: topic_id, slos (list of SLORead)

`service.py` — add:
- `list_slos(curriculum, grade?, subject?, db)` → list[SLO]
- `get_topic_slos(topic_id, db)` → list[SLO]
- `import_slos(curriculum, slos_data, db)` → {imported, updated}
- `map_topic_slos(topic_id, slo_codes, curriculum, db)` → list[TopicSLO]

### Tests

File: `server/tests/test_data_bank.py`
- Import SLOs for NCP — returns imported count
- List SLOs filtered by grade + subject
- Client A (NCP) cannot see SNC SLOs
- Map SLOs to topic — GET topic SLOs returns them
- Books filtered by client curriculum automatically
- Client (NCP) cannot see SNC books

### Frontend

- `webapp/app/dashboard/curriculum/page.tsx` — remove curriculum filter dropdown; books auto-filter by client curriculum
- Add SLO display to topic detail view (when user drills down to a topic, show mapped SLOs)
- Admin import page (`/dashboard/admin/import/page.tsx`) — add SLO import section

## Bead

- ID: `feat-step2-data-bank`
- Title: Step 2 — Data Bank (Books + SLOs)
- Category: feature

## Risks & constraints

- Staging DB is clean (no legacy books), so the ICT→NCP/Punjab→SNC UPDATE is a no-op; still included for production safety
- `topic_slos` depends on `topics` and `slos` both existing; run after both tables are set up
- SLO import is admin-only; clients can only read SLOs for their curriculum
- `GET /api/v1/books` currently accepts a `curriculum` query param — removing it is a breaking change for existing API consumers (acceptable per no-backwards-compat decision)

## E2E test scenarios

1. Client (NCP) calls `GET /api/v1/books` → only NCP books returned (no curriculum param needed)
2. Admin imports SLOs for NCP → `GET /api/v1/slos?grade=3&subject=Eng` returns them
3. Admin maps SLOs to topic → `GET /api/v1/topics/{id}/slos` returns mapped SLOs
4. Client (SNC) cannot see NCP SLOs
5. Admin import page shows SLO import form and success count
