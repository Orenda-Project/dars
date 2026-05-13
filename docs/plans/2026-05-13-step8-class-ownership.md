---
type: plan
last_verified: 2026-05-13
owner: hataf
---

# Plan: Step 8 — Class Ownership Restructure

## What this does

Moves class creation from the dashboard (client-owned) to the teacher app (teacher-owned). When a teacher creates a class by picking grade + subject, the system auto-resolves everything downstream: client curriculum → correct book → default chapter plan → AI lesson breakdown. The teacher walks away with a fully planned class.

The dashboard retains only client-level config: API keys, academic year, holidays, curriculum selection, and chapter plan defaults.

## Why

Classes belong to teachers, not clients. The current setup forces a client/admin to create classes on behalf of teachers, which breaks the product model. The correct flow is: client sets the curriculum once → teachers create their own classes and get everything auto-resolved.

## Ownership split (after this step)

| Thing | Owner | Where |
|-------|-------|--------|
| API keys | Client | Dashboard |
| Academic year + holidays | Client | Dashboard |
| Curriculum selection | Client | Dashboard |
| Chapter plan defaults (order + days per chapter) | Client | Dashboard |
| Classes (grade + section) | Teacher | Teacher App |
| Subject assignment (CST) | Teacher | Teacher App |
| Timetable | Teacher | Teacher App |
| Lesson breakdown (auto-generated) | System | Auto on class creation |

## What changes

### Backend — new endpoint

`POST /api/v1/teacher/classes`

Called from the teacher app. Creates a SchoolClass + ClassSubjectTeacher in one shot, then auto-triggers lesson slot generation.

Request body:
```json
{
  "grade": 5,
  "section": "A",
  "subject": "english",
  "academic_year_id": "uuid"
}
```

Flow:
1. Create `SchoolClass` (grade, section, name=`Grade {grade}-{section}`, client_id, academic_year_id)
2. Resolve book: find Book where `curriculum = client.curriculum AND grade = grade AND subject = subject` — if none, return 422 with "No book configured for this grade/subject"
3. Create `ClassSubjectTeacher` (class_id, subject, teacher_id = client.default_teacher_id, book_id)
4. Load default `ChapterPlan` rows: call `get_prefill_chapter_plans(client_id, book_id)` — these are the client's default chapter schedule
5. Upsert those chapter plans for this CST
6. For each chapter plan, fire `ai_breakdown_chapter` as a background task (same function used in Step 5)
7. Return: `{class_id, cst_id, chapter_count, status: "breakdown_pending"}`

Response schema `TeacherClassCreated`:
```python
class TeacherClassCreated(BaseModel):
    class_id: uuid.UUID
    cst_id: uuid.UUID
    chapter_count: int
    status: str  # "breakdown_pending"
```

### Backend — existing endpoints to keep as-is

All existing school endpoints (`POST /api/v1/school-classes`, `POST /api/v1/class-subject-teachers`, etc.) remain — they're used by existing tests and potentially external clients. The new endpoint is additive.

### Dashboard — curriculum-demo page restructure

The current `curriculum-demo` page has a 5-step wizard (Academic Year → Holidays → Classes → Subjects → Timetable) that does everything. Strip it down to client-only steps:

**Keep in dashboard wizard:**
- Step 1: Academic Year (create/select)
- Step 2: Holidays
- Step 3: Chapter Plan defaults (existing prefill UI — already there)

**Remove from dashboard wizard:**
- Step 3 (old): Classes creation → move to teacher app
- Step 4 (old): Subject assignment → move to teacher app  
- Step 5 (old): Timetable → move to teacher app

The dashboard curriculum page becomes a 3-step setup: Academic Year → Holidays → Chapter Plan. Clean, client-scoped.

### Teacher App — class creation flow

Add a "Create Class" button to `/teacher-app/classes/page.tsx`.

Simple form (modal or inline):
- Academic year selector (GET /api/v1/academic-years — client's years)
- Grade (dropdown: 1–12)
- Section (text: A, B, C...)
- Subject (dropdown from lookup API)

On submit → POST `/api/v1/teacher/classes` → optimistic add to list → show "Breakdown generating..." badge on the new class card → poll until slots appear.

Empty state update: if no academic year exists yet → show "Your school admin needs to set up the academic year first. Ask them to complete setup in the dashboard." (instead of current generic message)

### Tests

File: `server/tests/test_teacher_class_creation.py`

- Create class → SchoolClass + CST created, chapter plans upserted, breakdown triggered
- No book configured for grade/subject → 422
- No academic year → 422
- Client isolation: cannot create class for another client's academic year
- Duplicate class (same grade+section+subject+year) → 409

## Bead

- ID: `feat-step8-class-ownership`
- Title: Step 8 — Class Ownership Restructure
- Category: feature

## Risks & constraints

- `get_prefill_chapter_plans` requires a book to be imported for the client's curriculum+grade+subject. If no book exists, the endpoint must fail gracefully with a clear message — not a 500.
- Background breakdown tasks fire immediately on class creation. If the teacher creates 3 classes quickly, 3 × N breakdown tasks fire in parallel — acceptable at this scale.
- The existing 5-step wizard in curriculum-demo has a lot of state. When stripping class/subject/timetable steps, be careful not to break the academic year and holiday flows — they're the same component.
- `default_teacher_id` is used as the teacher for all teacher-app-created classes. If it's null, the endpoint must return 422 with "No default teacher configured — complete dashboard setup first."

## E2E test scenarios

1. Dashboard: complete 3-step setup (academic year + holidays + chapter plan) — classes section gone
2. Teacher app → My Classes → "Create Class" → pick grade 5 English → card appears with "Breakdown generating..." → refreshes to show lesson slots
3. Teacher app → class with no book configured → clear error message
4. Teacher app → class detail → lessons already populated (from auto-breakdown)
