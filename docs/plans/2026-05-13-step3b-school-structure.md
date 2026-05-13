---
type: plan
last_verified: 2026-05-13
owner: hataf
---

# Plan: Step 3b — School Structure (Teachers, Classes, Subjects, Timetable)

## What this does

Client sets up their school structure: teachers, classes, subject-teacher assignments, and weekly timetable. This is the "who teaches what, when" layer that sits between the academic calendar and the chapter plan.

## Why

Before chapters can be mapped to teaching days, we need to know: which classes exist, which teacher teaches which subject to which class, and on which days of the week. Without this, there's no basis for computing per-class teaching day sequences.

## What changes

Most of this already exists (`teachers/`, `school_classes`, `class_subject_teachers`, `timetables`). This step is about cleaning up and wiring into the dashboard.

### DB

Migration: `server/src/dars/migrations/20260513000004_school_structure.sql`

```sql
-- Auto-create default teacher on client signup (handled at app layer, not DB)
-- Ensure default_teacher_id FK is properly set
ALTER TABLE clients
  ADD CONSTRAINT clients_default_teacher_fkey
  FOREIGN KEY (default_teacher_id) REFERENCES teachers(id) ON DELETE SET NULL;
```

### Backend — `teachers/` module (minor cleanup)

- `POST /api/v1/teachers` — unchanged
- `GET  /api/v1/teachers` — unchanged (search, limit, offset)
- `GET  /api/v1/teachers/{id}` — unchanged
- `PATCH /api/v1/teachers/{id}` — unchanged

Auth service change: on `POST /auth/signup`, after creating client:
1. Auto-create a `Teacher` row: `{client_id, name: client.name, email: client.email}`
2. Set `client.default_teacher_id = teacher.id`

### Backend — `school/` module (structure portion, no changes to models)

Existing endpoints (keep, no changes):
- `POST /api/v1/classes` — create class (academic_year_id, grade, section, name)
- `GET  /api/v1/classes` — list (filter: academic_year_id?)
- `GET  /api/v1/classes/{id}` — get with subjects
- `POST /api/v1/classes/{id}/subjects` — assign subject + teacher + book
- `PATCH /api/v1/classes/{id}/subjects/{cst_id}` — update teacher or book
- `POST /api/v1/classes/{id}/subjects/{cst_id}/timetable` — set weekly schedule
- `GET  /api/v1/classes/{id}/subjects/{cst_id}/timetable` — get schedule

### Tests

File: `server/tests/test_school_structure.py`
- Signup → default teacher auto-created → `client.default_teacher_id` set
- Create class linked to academic year
- Assign subject + teacher + book to class
- Set timetable (Mon/Wed/Fri) → verify stored correctly
- Cannot assign teacher from different client
- Cannot assign book from different curriculum

### Frontend

Dashboard setup flow — new step after calendar:

**Step: Teachers**
- List existing teachers
- "Add Teacher" form: name, email (optional), phone (optional)
- Default teacher shown with a badge

**Step: Classes**
- "Add Class" form: grade selector, section (A/B/C), custom name
- List of created classes

**Step: Subjects & Timetable** (per class)
- For each class: assign subjects
- Per subject: pick teacher from list, pick book from client's curriculum books
- Per subject: pick days of week (checkboxes Mon–Fri), optional time

These steps wire into the existing `curriculum-demo` setup wizard, replacing the current mixed-concern wizard with a clean sequential flow.

## Bead

- ID: `feat-step3b-school-structure`
- Title: Step 3b — School Structure
- Category: feature

## Risks & constraints

- Default teacher FK now enforced at DB level — migration must run after teachers table exists (already true)
- Book assignment in CST must be from the client's curriculum (validate at service layer)
- Teacher assignment in CST must be from the same client (validate at service layer)
- Timetable `day_of_week` is 0=Mon…6=Sun — UI should show Mon–Fri only (Sat/Sun not typical school days but not blocked)

## E2E test scenarios

1. Signup → check default teacher auto-created and linked
2. Create class Grade 3-A → appears in class list
3. Assign English + teacher + book to Grade 3-A → CST created
4. Set timetable Mon/Wed/Fri → `GET timetable` returns 3 rows
5. Try assigning a teacher from wrong client → 403
6. Dashboard: complete teacher + class + subject + timetable setup flow end-to-end
