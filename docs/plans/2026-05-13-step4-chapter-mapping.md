---
type: plan
last_verified: 2026-05-13
owner: hataf
---

# Plan: Step 4 — Chapter Mapping & Year Plan

## What this does

Books are mapped onto the academic year per class. Each chapter gets a position (order in the year) and a teaching day count. Admin provides curriculum-level defaults (suggested day counts per chapter for NCP/SNC). Client sees these defaults pre-filled and can override per class.

## Why

The chapter plan is the year plan — it defines when each chapter starts and ends for a given class. Without it, there's no basis for lesson slot scheduling (Step 5) or LP generation (Step 6). Admin defaults mean clients don't start from scratch; they adjust rather than invent.

## What changes

### DB

Migration: `server/src/dars/migrations/20260513000006_chapter_mapping.sql`

```sql
-- Admin-level chapter schedule defaults per curriculum
CREATE TABLE curriculum_chapter_schedule (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  curriculum            TEXT NOT NULL REFERENCES curriculums(code),
  book_id               UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  chapter_id            UUID NOT NULL REFERENCES book_chapters(id) ON DELETE CASCADE,
  suggested_teaching_days INT NOT NULL,
  suggested_position    INT NOT NULL,
  term                  TEXT,    -- e.g. "Term 1", "Term 2" — informational only
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (curriculum, chapter_id)
);
```

Existing tables — no changes:
- `chapter_plans` — already correct (cst_id, chapter_id, position, teaching_days)

### Backend — admin endpoints (new, in `curriculum/` module)

- `POST /admin/curriculum/{code}/chapter-schedule` — bulk upsert defaults
  - Body: `[{book_id, chapter_id, suggested_teaching_days, suggested_position, term?}]`
  - Upserts by `(curriculum, chapter_id)`
- `GET  /admin/curriculum/{code}/chapter-schedule` — list all defaults for a curriculum
  - Returns: chapter title, book title, suggested_teaching_days, suggested_position, term

### Backend — client endpoints (update `school/` module)

- `GET /api/v1/classes/{id}/subjects/{cst_id}/chapter-plans/prefill`
  - New endpoint — returns chapters for the assigned book, pre-filled with curriculum defaults
  - Response: `[{chapter_id, title, chapter_number, suggested_teaching_days, suggested_position, term}]`
  - Client uses this to seed their chapter plan setup UI

- `POST /api/v1/classes/{id}/subjects/{cst_id}/chapter-plans` — unchanged (bulk upsert)
  - Client submits their final overrides; this creates/updates `chapter_plans` rows

- `GET  /api/v1/classes/{id}/subjects/{cst_id}/chapter-plans` — update response
  - Add `suggested_teaching_days` and `suggested_position` from curriculum defaults (for reference)
  - Add computed `start_date`, `end_date` (from `compute_chapter_date_ranges`)

- `PATCH /api/v1/chapter-plans/{id}` — unchanged (update teaching_days or position)

### Backend — service additions (`school/service.py`)

- `get_prefill_chapter_plans(cst_id, db)` → list of chapters with curriculum defaults merged in

### Tests

File: `server/tests/test_chapter_mapping.py`
- Admin bulk upserts curriculum chapter schedule → GET returns them
- Client prefill endpoint returns chapters with suggested days filled from curriculum defaults
- Client submits chapter plans (overriding some days) → stored correctly
- Chapter date ranges computed correctly: chapter 1 start = first teaching day, end = after N teaching days
- Client with no timetable set: date ranges fall back to Mon–Fri
- Client cannot see another client's chapter plans

### Frontend

Dashboard — "Syllabus" setup step (within planner setup flow):

1. Class + subject selector (from previously set up CSTs)
2. Load prefill from `GET .../chapter-plans/prefill`
3. Show chapter list with: chapter number, title, suggested days (from curriculum), editable override days input
4. Drag to reorder chapters (updates position)
5. "Save Syllabus" → POST bulk upsert
6. After save: show calendar view with chapters mapped to date ranges
   - Each chapter shown as a colored span on the calendar
   - Teaching days count shown per chapter

## Bead

- ID: `feat-step4-chapter-mapping`
- Title: Step 4 — Chapter Mapping & Year Plan
- Category: feature

## Risks & constraints

- `curriculum_chapter_schedule` defaults are per curriculum, not per client — admin enters them once, all clients of that curriculum benefit
- Prefill endpoint requires the CST to have a `book_id` set — if no book assigned, return empty list with a clear message
- Chapter date range computation requires both timetable and academic year to be set — if either is missing, return null dates with a warning
- Teaching day count per chapter must be ≥ 1 (validate at service layer)
- Position must be unique within a CST's chapter plan — enforce at DB level (already has UNIQUE constraint on cst_id + chapter_id)

## E2E test scenarios

1. Admin sets curriculum defaults for NCP English Grade 3 (10 chapters)
2. Client (NCP) sets up Grade 3-A English with Mon/Wed/Fri timetable
3. Client loads prefill → sees 10 chapters with suggested days pre-filled
4. Client overrides Chapter 1 from 8 days to 10 days → saves
5. Calendar view shows Chapter 1 spanning correct date range (Mon/Wed/Fri only)
6. Drag Chapter 2 above Chapter 1 → positions swap, date ranges update
