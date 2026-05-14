---
type: plan
last_verified: 2026-05-14
owner: hataf
---

# Plan: Unified Sequence Calendar

## What this does

The breakdown algorithm produces a single ordered sequence of periods (lessons + formative assessments interleaved) numbered Day 1…Day N across the full academic year. Each day number maps 1:1 to an academic day: Day 1 = first teaching day of the year, Day 2 = second, etc. The calendar service computes all dates from this global sequence — no stored `scheduled_date`, no timetable filtering. Every academic day (Mon–Fri, excluding holidays) is a teaching day.

## Why

Previously assessments had a `scheduled_date` set to `date.today()` as a placeholder, and lesson slot dates were computed per-chapter using a timetable filter. The user confirmed: timetable is all academic days for now; the breakdown owns the full sequence; dates are derived, not stored.

## What changes

### Backend

- **`server/src/dars/school/models.py`**
  - `AssessmentSlot`: add `day_number: Mapped[int | None]` column; make `scheduled_date` nullable (`Mapped[date | None]`)

- **`server/src/dars/school/service.py`**
  - `compute_teaching_days()`: remove timetable filter — always walk Mon–Sat (0–5) excluding holidays. This is the global academic day list, same for every CST in the same academic year.
  - `ai_breakdown_chapter()`: accept a `global_day_offset: int` parameter. Number slots globally (lesson `day_number = offset + item["day"]`, assessment `day_number = offset + item["day"]`). Store `day_number` on `AssessmentSlot`; set `scheduled_date = None`.
  - `ai_breakdown_all()`: track running `offset` across chapters; pass it to each `ai_breakdown_chapter()` call.
  - `get_calendar_week()`: replace timetable-based filtering with academic-day-based date computation. Build a global `day_number → date` lookup from `compute_teaching_days()`. For each CST, fetch all lesson slots and assessment slots with `day_number` in the week's range. Emit one period per slot in the week. Remove the `_nth_timetable_day` helper (no longer needed).
  - Remove `auto_schedule_formative_assessments()` — breakdown now owns FA placement.

- **`server/src/dars/school/schemas.py`**
  - `AssessmentSlotRead`: make `scheduled_date` optional (`date | None`)
  - `AssessmentSlotCreate`: keep `scheduled_date` as required (manual scheduling path, used only in tests for now)

### DB

- **Migration: `server/src/dars/migrations/20260514000001_assessment_slot_day_number.sql`**
  ```sql
  ALTER TABLE assessment_slots ADD COLUMN IF NOT EXISTS day_number INTEGER;
  ALTER TABLE assessment_slots ALTER COLUMN scheduled_date DROP NOT NULL;
  ```

### Tests

- **`server/tests/test_teacher_app.py`**
  - `test_calendar_week_includes_assessments`: rewrite to use breakdown instead of manually posting an assessment slot with a `scheduled_date`. Run `ai_breakdown_chapter` (or mock it), verify the calendar returns the FA on the correct academic day.
  - `test_calendar_week_client_isolation`: same — derive isolation from breakdown sequence, not manual `scheduled_date`.
  - Remove timetable setup steps from calendar tests (timetable no longer drives calendar).

- **`server/tests/test_lesson_breakdown.py`**
  - Add test: `ai_breakdown_all` assigns globally incrementing `day_number` across chapters (no per-chapter reset).
  - Add test: assessment slots produced by breakdown have `day_number` set and `scheduled_date = None`.

## Bead
- ID: `feat-unified-sequence-calendar`
- Title: Unified sequence calendar — day_number drives all date mapping
- Category: feature

## Risks & constraints

- `scheduled_date` is `NOT NULL` in prod — migration must use `DROP NOT NULL` cleanly (no existing rows will break; existing FAs had placeholder dates anyway).
- `compute_teaching_days()` currently falls back to Mon–Fri if no timetable rows exist. After this change it always uses Mon–Sat (0–5) minus holidays. Existing CSTs with timetable rows will now ignore those rows for date computation — this is intentional.
- `auto_schedule_formative_assessments()` is called from the router. Once breakdown owns FAs, this endpoint becomes a no-op or should be removed. Keep the endpoint but return an empty list to avoid breaking existing clients.
- Calendar tests that manually POST assessment slots with `scheduled_date` will need to be rewritten around the breakdown sequence.
- `_nth_timetable_day` helper can be deleted once calendar uses the global day list directly.

## E2E test scenarios

1. Create a class with academic year (e.g. 2026-04-01 → 2027-03-31), run breakdown-year → verify calendar shows lessons and FAs on correct academic dates starting from year start.
2. Add a holiday mid-year → verify the holiday date is skipped in the sequence (Day N shifts to next working day).
3. Navigate calendar week-by-week → verify each day shows exactly one period per class when breakdown exists, and "No plan yet" when it doesn't.
