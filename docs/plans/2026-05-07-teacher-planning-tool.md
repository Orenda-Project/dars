---
type: plan
last_verified: 2026-05-07
owner: hataf
---

# Plan: Teacher Planning Tool

## What this does

A fully functional, multi-tenant teacher planning system. The client (admin) sets up an academic calendar, creates classes, assigns teachers to class-subject pairs, and the system builds a year plan: chapters mapped to teaching days, lesson slots auto-generated, formative assessments auto-scheduled. The teacher sees "today's classes", what to teach next in each class, marks lessons as taught, and the SLO tracker updates in real time. All data is per `client_id`.

## Why

Replace the static `/dashboard/curriculum-demo` prototype with a real backend so the tool can be tested with actual teachers in an actual school year.

## Personas

- **Client / Admin** — the school network. Uses existing API key. Manages setup: academic calendar, classes, teacher-class assignments.
- **Teacher** — has an existing `Teacher` record. No separate login for this prototype — teacher views are accessed via the client session.

## What changes

---

### Backend — new module: `school/`

All new models go in `server/src/dars/school/`. Registered in `main.py`. All DB queries filtered by `client_id`.

#### Models

**`AcademicYear`** (`academic_years`)
```
id          uuid PK
client_id   uuid FK clients
name        text  — e.g. "2026–27"
start_date  date
end_date    date
created_at  timestamptz
```

**`Holiday`** (`holidays`)
```
id              uuid PK
client_id       uuid FK clients
academic_year_id uuid FK academic_years
date            date
name            text  — e.g. "Eid ul-Fitr"
```

**`SchoolClass`** (`school_classes`)
```
id              uuid PK
client_id       uuid FK clients
academic_year_id uuid FK academic_years
grade           int
section         text  — e.g. "A"
name            text  — e.g. "Grade 3-A"  (computed or user-set)
start_date      date nullable  — defaults to academic_year.start_date
end_date        date nullable  — defaults to academic_year.end_date
created_at      timestamptz
```

**`ClassSubjectTeacher`** (`class_subject_teachers`) — links a class to a subject and a teacher
```
id          uuid PK
client_id   uuid FK clients
class_id    uuid FK school_classes
subject     text  FK subjects
teacher_id  uuid FK teachers nullable  — teacher may not be assigned yet
book_id     uuid FK books nullable     — which book this class uses
created_at  timestamptz
UNIQUE (class_id, subject)
```

**`Timetable`** (`timetables`) — weekly recurring schedule per class-subject
```
id                      uuid PK
client_id               uuid FK clients
class_subject_teacher_id uuid FK class_subject_teachers
day_of_week             int   — 0=Mon … 6=Sun
start_time              time nullable
end_time                time nullable
created_at              timestamptz
```

**`ChapterPlan`** (`chapter_plans`) — a class's allocation of days to a chapter
```
id                      uuid PK
client_id               uuid FK clients
class_subject_teacher_id uuid FK class_subject_teachers
chapter_id              uuid FK book_chapters
position                int   — ordering within the year plan
teaching_days           int   — how many teaching days allocated
created_at              timestamptz
updated_at              timestamptz
UNIQUE (class_subject_teacher_id, chapter_id)
```

**`ClassLessonSlot`** (`class_lesson_slots`) — one lesson slot per class (distinct from global `lesson_slots`)
```
id                      uuid PK
client_id               uuid FK clients
class_subject_teacher_id uuid FK class_subject_teachers
chapter_plan_id         uuid FK chapter_plans
day_number              int
lp_type                 text  — e.g. "Reading", "Grammar", "Revision"
title                   text
lesson_plan_id          uuid FK lesson_plans nullable
status                  text  — planned | taught | skipped  default: planned
taught_date             date nullable
created_at              timestamptz
```

**`AssessmentSlot`** (`assessment_slots`) — scheduled assessments per class
```
id                      uuid PK
client_id               uuid FK clients
class_subject_teacher_id uuid FK class_subject_teachers
chapter_plan_id         uuid FK chapter_plans nullable  — null for summatives not tied to a chapter
assessment_type         text  — formative | summative
scheduled_date          date
title                   text nullable
exam_generation_id      uuid FK custom_exam_generations nullable
status                  text  — scheduled | generated | completed | skipped  default: scheduled
created_at              timestamptz
updated_at              timestamptz
```

---

#### Migration

File: `server/src/dars/migrations/20260507000001_teacher_planning.sql`

Creates all 7 tables above in order (FK dependencies respected).

---

#### API endpoints — new router `school/router.py`

All require `X-API-Key`. All filter by `client_id`.

**Academic years**
- `POST /api/v1/academic-years` — create
- `GET  /api/v1/academic-years` — list
- `POST /api/v1/academic-years/{id}/holidays` — add holiday
- `GET  /api/v1/academic-years/{id}/holidays` — list holidays
- `DELETE /api/v1/academic-years/{id}/holidays/{hid}` — remove holiday

**Classes**
- `POST /api/v1/classes` — create class
- `GET  /api/v1/classes` — list (optionally filter by `academic_year_id`)
- `GET  /api/v1/classes/{id}` — get with subjects/teachers
- `POST /api/v1/classes/{id}/subjects` — assign subject+teacher+book to a class
- `PATCH /api/v1/classes/{id}/subjects/{cst_id}` — update teacher or book
- `POST /api/v1/classes/{id}/subjects/{cst_id}/timetable` — set weekly schedule (replaces existing)
- `GET  /api/v1/classes/{id}/subjects/{cst_id}/timetable` — get schedule

**Chapter plans**
- `POST /api/v1/classes/{id}/subjects/{cst_id}/chapter-plans` — bulk upsert ordered chapter list with day allocations
- `GET  /api/v1/classes/{id}/subjects/{cst_id}/chapter-plans` — list with computed date ranges (teaching days derived from timetable + academic calendar holidays)
- `PATCH /api/v1/chapter-plans/{id}` — update teaching_days or position

**Lesson slots (per class)**
- `POST /api/v1/chapter-plans/{id}/lesson-slots/generate` — AI-generate lesson sequence for a chapter plan (uses existing `lp_type` distribution logic from curriculum-demo). Returns list of `ClassLessonSlot`.
- `GET  /api/v1/chapter-plans/{id}/lesson-slots` — list slots
- `PATCH /api/v1/class-lesson-slots/{id}/mark-taught` — mark as taught, set `taught_date = today`
- `PATCH /api/v1/class-lesson-slots/{id}` — update lp_type, title, or lesson_plan_id

**Assessment slots**
- `POST /api/v1/classes/{id}/subjects/{cst_id}/assessment-slots/auto-schedule` — compute and persist FA slots (one per chapter, day after last teaching day). Idempotent.
- `POST /api/v1/classes/{id}/subjects/{cst_id}/assessment-slots` — manually add summative
- `GET  /api/v1/classes/{id}/subjects/{cst_id}/assessment-slots` — list all
- `PATCH /api/v1/assessment-slots/{id}` — update scheduled_date, status, title
- `DELETE /api/v1/assessment-slots/{id}` — remove

**Today's view**
- `GET /api/v1/today` — returns all class-subject pairs scheduled for today (based on timetable day_of_week). Each entry includes: class name, subject, teacher name, current lesson slot (next `planned` slot), previous taught slot, next planned slot after current.

---

#### Service layer — `school/service.py`

Key functions:
- `compute_teaching_days(cst_id, db)` — given a `ClassSubjectTeacher`, walks the timetable (days of week) across the academic year, removes holidays and weekends, returns ordered list of teaching dates.
- `compute_chapter_date_ranges(cst_id, db)` — uses `compute_teaching_days` + `ChapterPlan.position` + `ChapterPlan.teaching_days` to assign a start/end date to each chapter.
- `auto_schedule_formative_assessments(cst_id, db)` — for each chapter plan, finds the first teaching day after the chapter ends, upserts an `AssessmentSlot(assessment_type="formative")`.
- `generate_lesson_sequence(chapter_plan_id, db)` — distributes LP types across `teaching_days` using the same algorithm as the demo (subject-aware cycle, last slot = Revision), creates `ClassLessonSlot` rows.

---

### Tests

File: `server/tests/test_school.py`

Scenarios:
- Create academic year, add holidays
- Create class, assign subject+teacher+book
- Set timetable (Mon/Wed/Fri), verify `compute_teaching_days` excludes weekends + holidays
- Bulk upsert chapter plans, verify date ranges
- Generate lesson sequence, verify slot count matches `teaching_days`
- Mark slot as taught, verify status + date
- Auto-schedule FAs, verify one per chapter on correct date
- `GET /today` returns only today's scheduled classes
- All endpoints 403 if wrong `client_id`

---

### Frontend — `/dashboard/curriculum-demo/page.tsx`

Replace all static data with real API calls. Keep the 5-tab structure but wire everything to the backend. Add a 6th tab and setup flow.

#### Setup flow (new — shown when no academic year exists for client)

A setup wizard surfaced before the tabs load:
1. **Academic Year** — name, start date, end date
2. **Holidays** — add holiday dates (name + date), skip option
3. **Classes** — add one or more classes (grade + section)
4. **Subjects** — for each class, assign subjects, pick a teacher, pick a book
5. **Timetable** — for each class-subject, pick days of week (time optional)

Once setup is complete, the planner loads.

#### Tab: Classes (was static, now live)
- Lists real `SchoolClass` records from the API
- Click a class → shows its subjects, chapter progress, next lesson

#### Tab: Syllabus (was static, now live)
- Loads `ChapterPlan` list from API with computed date ranges
- List view: chapters with date ranges + day count. Drag-to-reorder updates `position` via PATCH. Resize (change `teaching_days`) inline.
- Calendar view: real teaching days per the timetable (not all weekdays). Chapter color spans. FA markers (amber) and summative markers (rose) on their scheduled dates.
- "+ Auto-schedule FAs" button calls `auto-schedule` endpoint
- "+ Add Summative" inline form → POST assessment slot

#### Tab: Lesson Breakdown (was static, now live)
- Loads `ClassLessonSlot` list for selected class+chapter
- "Generate Lesson Breakdown" button calls `/generate` endpoint
- Each slot shows LP type, title, status badge
- "Mark as Taught" button on each slot → PATCH mark-taught
- "View LP" opens existing LP panel slide-over

#### Tab: SLO Tracker (remains mostly static for now)
- Subject selector still works; data still static
- Coverage derived from `taught` slots: topics linked to sub-SLOs counted as covered

#### Tab: Assessments (new)
- Lists all `AssessmentSlot` rows for selected class+subject
- Columns: Chapter, Type (FA/SA), Scheduled date, Status, Action
- Status update inline (dropdown: scheduled → completed / skipped)
- "Generate" button → POST to existing `/custom-exam-generations` endpoint (wired up but not required for MVP)

#### Tab: Today (new — default tab)
- Calls `GET /api/v1/today`
- Card per class scheduled today: class name, subject, teacher
- Previous lesson, current lesson (with LP button), next lesson
- "Mark as Taught" on current lesson

---

### No changes to existing features

- `lesson_plans`, `assessments`, `student_assessments`, `exam_generations` — untouched
- `curriculum` module (Books, Chapters, Topics, LessonSlots) — untouched
- Existing LP generation flow — untouched
- Sidebar — move `curriculum-demo` from Beta to main nav (rename label to "Planner")

---

## Bead

- ID: `feat-teacher-planning-tool`
- Title: Teacher Planning Tool — full stack
- Category: feature

## Risks & constraints

- `LessonSlot` (global, used by LP generation) vs `ClassLessonSlot` (per-class, used by planner) — these are distinct models. Do not confuse them.
- Teaching day computation must handle classes where timetable hasn't been set yet — fall back to all weekdays minus holidays.
- `compute_teaching_days` is called at read time for chapter date ranges; it's not stored. This is fine for the prototype — it's a cheap loop over dates.
- Migration must not touch any existing tables.
- Keep all new endpoints behind `X-API-Key` + `client_id` filter — same as everything else.
- `last_verified` on `docs/conventions.md` should be updated after this lands with any new gotchas.

## E2E test scenarios

1. Setup wizard → create academic year + 2 holidays + 1 class + English subject + timetable (Mon/Wed/Fri)
2. Syllabus tab → chapter plans appear with correct date ranges (holidays excluded)
3. Resize a chapter → date ranges update downstream
4. Auto-schedule FAs → amber markers appear on calendar
5. Add summative assessment → rose marker appears on calendar + row in Assessments tab
6. Lesson Breakdown tab → generate lesson sequence for a chapter → slots appear
7. Mark a slot as taught → status badge updates, SLO tracker coverage increments
8. Today tab → if today is a scheduled day, the correct class and lesson appear
9. Two clients — Client A cannot see Client B's classes or lesson slots
