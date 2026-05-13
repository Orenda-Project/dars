---
type: plan
last_verified: 2026-05-13
owner: hataf
---

# Plan: Step 3 — Academic Calendar

## What this does

Client sets up their academic year: session start/end, holidays. The system computes which days are teaching days (excluding weekends and holidays). Dashboard provides a clean setup flow for this. No exam periods yet — kept simple.

## Why

The academic calendar is the foundation of the teacher planning tool. Teaching day computation (which days are actual school days) is what drives chapter date ranges, lesson slot scheduling, and the teacher's "today" view. Everything in Steps 4+ depends on a correct calendar.

## What changes

Most of this already exists (`academic_years`, `holidays`, `compute_teaching_days` service function). This step is about:
1. Cleaning up what exists
2. Properly wiring it into the dashboard as a first-class setup flow
3. Ensuring the teaching day computation is solid and tested

### DB

Migration: `server/src/dars/migrations/20260513000005_academic_calendar.sql`

No new tables. Just ensure existing tables are clean:

```sql
-- Ensure academic_years has proper constraints
ALTER TABLE academic_years
  ADD CONSTRAINT academic_years_dates_check CHECK (end_date > start_date);

-- Ensure holidays are within the academic year (enforced at app level, not DB)
-- No DB change needed for holidays
```

### Backend — clean up `school/` module (calendar portion)

`school/service.py` — `compute_teaching_days(cst_id, db)`:
- Existing function: walks dates from class start to end, removes weekends + holidays
- Add: fallback if no timetable set → use Mon–Fri as default
- Add: timezone-safe date comparison (use `date` objects, not `datetime`)
- Add: return type annotation `list[date]`

New endpoint:
- `GET /api/v1/academic-years/{id}/teaching-days` — returns count of teaching days in the year (excluding weekends + holidays). Useful for client to understand how many days they have total.

Existing endpoints (keep, no changes):
- `POST /api/v1/academic-years`
- `GET  /api/v1/academic-years`
- `POST /api/v1/academic-years/{id}/holidays`
- `GET  /api/v1/academic-years/{id}/holidays`
- `DELETE /api/v1/academic-years/{id}/holidays/{hid}`

### Tests

File: `server/tests/test_academic_calendar.py` (update existing)
- Create academic year → verify dates stored correctly
- Add holiday → verify excluded from teaching days
- `compute_teaching_days` excludes weekends
- `compute_teaching_days` excludes holidays
- `compute_teaching_days` falls back to Mon–Fri if no timetable
- `GET /api/v1/academic-years/{id}/teaching-days` returns correct count
- Client isolation: cannot see another client's academic year

### Frontend

`webapp/app/dashboard/curriculum-demo/page.tsx` — the setup wizard already has academic year + holidays steps. Clean up:
- Step 1 (Academic Year): name, start date, end date → show computed teaching day count after save
- Step 2 (Holidays): add holiday dates with names → calendar preview updates in real time showing which days are teaching days (green) vs holidays (grey) vs weekends (light grey)
- Remove all other wizard steps from this page — they move to later steps

New component: `components/molecules/dashboard/calendar-preview.tsx`
- Mini calendar showing a month at a time
- Color-coded: teaching days (white), holidays (grey), weekends (light grey)
- Navigation: prev/next month

## Bead

- ID: `feat-step3-academic-calendar`
- Title: Step 3 — Academic Calendar
- Category: feature

## Risks & constraints

- `compute_teaching_days` is called at read time (not stored) — acceptable for now, it's a cheap loop
- Holiday dates must be within the academic year date range — validate at service layer, not just DB
- The dashboard currently conflates calendar setup with class/subject setup in one wizard — this step separates them

## E2E test scenarios

1. Create academic year (Sep 1 – Jun 30) → teaching day count shown
2. Add 3 holidays → teaching day count decreases by 3
3. Calendar preview shows correct color coding
4. Cannot create academic year where end_date ≤ start_date → validation error
5. Client A cannot see Client B's academic years
