---
type: plan
last_verified: 2026-05-13
owner: hataf
---

# Plan: Grades & Subjects Lookup Tables

## What this does

Replaces the hardcoded `mapping.py` with DB-backed `grades` and `subjects` tables. Each row stores a `code` (what assistants expect: `"Maths"`, `5`) and a `display_name` (what users see: `"Mathematics"`, `"Grade 5"`). Validation at API boundaries queries the DB instead of a hardcoded dict. A public endpoint lists all valid grades and subjects so the frontend can populate dropdowns dynamically. All subjects are valid for all curriculums (no curriculum-subject restriction).

## Why

- Removes the only remaining place where adding a new subject/grade requires a code change + redeploy
- Makes `slos.subject` a proper FK in Step 2 (SLOs), enforcing referential integrity
- Gives the school class setup UI in Step 3 a clean `/api/v1/subjects` and `/api/v1/grades` endpoint to populate dropdowns
- Consolidates the assistant-code translation to one place in the DB rather than scattered aliases

## What changes

### DB

Migration: `server/src/dars/migrations/20260513000003_grades_subjects.sql`

```sql
CREATE TABLE IF NOT EXISTS grades (
  code        INT PRIMARY KEY,
  display_name TEXT NOT NULL
);

INSERT INTO grades (code, display_name) VALUES
  (1, 'Grade 1'),
  (2, 'Grade 2'),
  (3, 'Grade 3'),
  (4, 'Grade 4'),
  (5, 'Grade 5')
ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS subjects (
  code         TEXT PRIMARY KEY,  -- assistant-expected code: "Eng", "Maths", "Urdu", etc.
  display_name TEXT NOT NULL       -- user-facing: "English", "Mathematics", "Urdu"
);

INSERT INTO subjects (code, display_name) VALUES
  ('Eng',     'English'),
  ('Maths',   'Mathematics'),
  ('Urdu',    'Urdu'),
  ('Science', 'Science'),
  ('GK',      'General Knowledge'),
  ('Islamiat','Islamiat'),
  ('SST',     'Social Studies')
ON CONFLICT (code) DO NOTHING;
```

### Backend — new module `server/src/dars/lookup/`

`models.py`:
- `Grade` model → `grades` table (`code` INT PK, `display_name` TEXT)
- `Subject` model → `subjects` table (`code` TEXT PK, `display_name` TEXT)

`service.py`:
- `get_all_grades(db) -> list[Grade]`
- `get_all_subjects(db) -> list[Subject]`
- `validate_grade(db, code: int) -> Grade` — raises 422 if not found
- `validate_subject(db, code: str) -> Subject` — raises 422 if not found

`schemas.py`:
- `GradeResponse(code: int, display_name: str)`
- `SubjectResponse(code: str, display_name: str)`

`router.py` — public endpoints (no auth required — these are reference data):
- `GET /api/v1/grades` → `list[GradeResponse]`
- `GET /api/v1/subjects` → `list[SubjectResponse]`

`__init__.py` — empty

### Backend — update `mapping.py`

Replace the entire file with thin wrappers that call the DB. Keep `canonical_grade` and `canonical_subject` as sync functions for backwards compatibility with Pydantic validators — but make them simple pass-throughs that only normalise case/whitespace. Move real validation (DB check) to the service layer.

Actually: the Pydantic `field_validator` in schemas runs before we have a DB session. So:

- `mapping.py` keeps `canonical_subject(v)` and `canonical_grade(v)` as **normalisation only** (lowercase strip, int cast) — no validation, no raising on unknown values
- Real validation moves to the service functions: `validate_grade(db, code)` and `validate_subject(db, code)` called in `create_generated_lp` / `create_generated_exam` before inserting

This is the correct layering: Pydantic normalises shape, service validates against DB.

### Backend — update `generated_lps/service.py`

In `create_generated_lp`: after receiving `data: GeneratedLPCreate`, call:
```python
await validate_grade(db, data.grade)
await validate_subject(db, data.subject)
```
Raises 422 if either is unknown. The `assistant_code` stored is `data.subject` (already the code) and `data.grade` (already the int).

### Backend — update `generated_exams/service.py`

Same pattern as generated_lps.

### Backend — update `curriculum/router.py`

Any call to `canonical_subject` / `canonical_grade` for validation: replace with `validate_subject` / `validate_grade` where a DB session is available. Normalisation calls can stay as-is.

### Backend — update `main.py`

Add:
```python
import dars.lookup.models  # noqa
from dars.lookup.router import router as lookup_router
...
app.include_router(lookup_router)
```

### Tests

`server/tests/test_lookup.py`:
- `GET /api/v1/grades` → 200, returns list with code + display_name, includes grade 5
- `GET /api/v1/subjects` → 200, returns list including Eng/Maths/Urdu
- No auth required on either endpoint

Update `server/tests/test_generated_lps.py`:
- Seed `grades` and `subjects` rows in `db_session` fixture (SQLite in-memory won't have them)
- Add test: unknown subject → 422
- Add test: unknown grade → 422

Update `server/tests/test_generated_exams.py`:
- Same seeding + same 422 tests

### Frontend

`webapp/app/dashboard/lesson-plans/page.tsx`:
- On mount, fetch `GET /api/v1/subjects` and `GET /api/v1/grades`
- Replace hardcoded `CURRICULUM_SUBJECTS` dict with API response
- Subject dropdown: `display_name` shown, `code` sent in request
- Grade dropdown: `display_name` shown (`"Grade 5"`), `code` (int) sent in request

`webapp/app/dashboard/exam-generator/page.tsx`:
- Same — fetch subjects + grades on mount, replace hardcoded options

## Bead

- ID: `feat-grades-subjects`
- Title: Grades & Subjects lookup tables
- Category: feature

## Risks & constraints

- Tests use SQLite in-memory — `grades` and `subjects` tables must be seeded in fixtures since migration data doesn't run in tests
- `mapping.py` remains but is reduced to normalisation only — do not delete it yet, `curriculum/router.py` imports it in several places and cleanup can be gradual
- `subjects.code` is the assistant-expected value — never store display names in `generated_lesson_plans.subject` or `generated_exams.subject`; always store the code

## E2E test scenarios

1. `GET /api/v1/grades` → list of 5 grades with display names
2. `GET /api/v1/subjects` → list of subjects with display names
3. Lesson Plans page → subject dropdown populated from API, not hardcoded
4. Exam Generator page → same
5. `POST /api/v1/lesson-plans` with unknown subject → 422
6. `POST /api/v1/lesson-plans` with unknown grade → 422
