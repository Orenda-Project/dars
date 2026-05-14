---
type: plan
last_verified: 2026-05-14
owner: hataf
---

# Plan: Teacher Calendar

## What this does

A `/teacher-app/calendar` page showing the teacher a weekly calendar with all their classes — which lesson (slot) is scheduled on which day, and which assessments are coming up. The teacher can navigate week by week and see what they need to teach/test and when.

## Why

Teachers with 20+ classes across multiple days need a unified view of their schedule beyond "today's classes". This lets them see the whole week at a glance: which class, which lesson, which day.

## Data model understanding

- `Timetable` rows: which `day_of_week` (0=Mon..5=Sat) a CST meets
- `ChapterPlan` + `compute_chapter_date_ranges()`: computes `start_date`/`end_date` per chapter for a CST
- `ClassLessonSlot`: each slot has a `day_number` (sequence 1..N within the chapter). Given the chapter's `start_date` and the CST's timetable days, slot N falls on the Nth teaching day from the chapter start
- `AssessmentSlot`: already has `scheduled_date`

## What changes

### Backend

- **File: `server/src/dars/school/schemas.py`** — Add:
  - `CalendarLessonEntry`: `date`, `cst_id`, `class_id`, `class_name`, `subject`, `slot_id`, `day_number`, `lp_type`, `title`, `status`, `lesson_plan_id`
  - `CalendarAssessmentEntry`: `date`, `cst_id`, `class_id`, `class_name`, `subject`, `slot_id`, `assessment_type`, `title`, `status`, `exam_id`
  - `CalendarDayResponse`: `date`, `lessons: list[CalendarLessonEntry]`, `assessments: list[CalendarAssessmentEntry]`
  - `CalendarResponse`: `items: list[CalendarDayResponse]`, `week_start: date`, `week_end: date`

- **File: `server/src/dars/school/service.py`** — Add `get_calendar_week(teacher_id: int, client_id: int, week_start: date, db: AsyncSession) -> list[dict]`:
  - Fetch all CSTs for the teacher
  - For each CST, fetch timetable days + chapter plans (with date ranges)
  - For each chapter plan, fetch its lesson slots; compute each slot's calendar date:
    - Start from chapter `start_date`; walk forward counting only the CST's timetable weekdays; slot N falls on the Nth occurrence
  - Fetch assessment slots for the CST; include those with `scheduled_date` in the week range
  - Return all events grouped by date within `[week_start, week_end]`

- **File: `server/src/dars/school/router.py`** — Add:
  ```
  GET /api/v1/me/calendar?week_start=YYYY-MM-DD
  ```
  - `week_start` defaults to current Monday if not provided
  - Calls service, returns `CalendarResponse`
  - Filters by `current_client.default_teacher_id`; returns empty if unset

### Frontend

- **File: `webapp/lib/school-api.ts`** — Add `CalendarLessonEntry`, `CalendarAssessmentEntry`, `CalendarDayResponse`, `CalendarResponse` types and `getCalendar(weekStart?: string): Promise<CalendarResponse>` function

- **File: `webapp/app/teacher-app/calendar/page.tsx`** — New page:
  - Week navigation: `<` / `>` buttons to go prev/next week; header shows e.g. "12 – 17 May 2026"
  - 6-column grid (Mon–Sat); each cell shows the day date + events
  - Lesson events: amber pill with class name + lesson title (truncated). On click: link to `/teacher-app/classes/[cst_id]`
  - Assessment events: red/violet pill with FA/SA + title. On click: link to `/teacher-app/classes/[cst_id]`
  - Empty day: faint dashed border, no content
  - Loading: skeleton columns
  - Mobile: scrollable horizontal grid or stacked by day (same component, `overflow-x-auto`)

- **File: `webapp/app/teacher-app/layout.tsx`** — Add "Calendar" link in the teacher-app sidebar/nav

### DB

No migrations required. All data is already in `timetables`, `chapter_plans`, `class_lesson_slots`, `assessment_slots`.

### Tests

- **File: `server/tests/test_teacher_app.py`** — Add:
  - `test_calendar_week_returns_lessons`: create CST + timetable (Mon/Wed) + chapter plan with `start_date` + lesson slots; verify `/api/v1/me/calendar` returns slots on correct dates
  - `test_calendar_week_includes_assessments`: create assessment slot with `scheduled_date`; verify it appears on that date
  - `test_calendar_week_empty_without_teacher`: client with no default_teacher_id gets empty calendar
  - `test_calendar_week_client_isolation`: two clients; each only sees their own events

## Bead

- ID: `feat-teacher-calendar`
- Title: Teacher calendar — weekly view with lessons + assessments
- Category: feature

## Risks & constraints

- Date computation (slot → calendar date) must handle gaps in timetable days correctly. If chapter starts Monday and timetable is Mon/Wed, slot 2 = Wednesday of same week; slot 3 = Monday next week.
- Chapters with no `start_date` (not yet scheduled) must be excluded — don't try to compute dates for them
- Slots with `day_number` beyond the chapter's range should be clamped/skipped gracefully
- The calendar only shows what's in range for the requested week; chapters starting after the week end are excluded

## E2E test scenarios

1. Navigate to `/teacher-app/calendar` — calendar loads with current week, shows today's column highlighted
2. Click `>` to advance to next week — events update
3. Lesson event pill is clickable — navigates to class detail page
4. Week with no events — shows empty grid, no crash
