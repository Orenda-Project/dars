---
type: plan
last_verified: 2026-05-13
owner: hataf
---

# Plan: Step 1 — Foundation (Clean DB + Auth + Curriculum)

## What this does

Wipes the entire database and rebuilds from scratch with a clean schema. Merges the split LP and exam modules into single client-scoped modules. Introduces a proper `curriculums` table (NCP, SNC) replacing the old curriculum strings. Every table is client-scoped and correctly isolated from the start.

## Why

The current schema has accumulated duplication, broken isolation (`lesson_plans` has no `client_id`), dead tables (`assessments`, `student_assessments`), and four modules doing two jobs. Rather than patch it, we drop everything and rebuild correctly. No backwards compatibility.

## What changes

### DB — Migration 1: Reset

File: `server/src/dars/migrations/20260513000001_reset.sql`

Drops every existing table and the `schema_migrations` tracking table itself, then exits. The next migration rebuilds from scratch.

```sql
-- Drop all tables in dependency order (children before parents)
DROP TABLE IF EXISTS schema_migrations CASCADE;
DROP TABLE IF EXISTS student_assessments CASCADE;
DROP TABLE IF EXISTS assessments CASCADE;
DROP TABLE IF EXISTS lesson_plan_edits CASCADE;
DROP TABLE IF EXISTS webhook_deliveries CASCADE;
DROP TABLE IF EXISTS class_lesson_slots CASCADE;
DROP TABLE IF EXISTS assessment_slots CASCADE;
DROP TABLE IF EXISTS chapter_plans CASCADE;
DROP TABLE IF EXISTS timetables CASCADE;
DROP TABLE IF EXISTS class_subject_teachers CASCADE;
DROP TABLE IF EXISTS school_classes CASCADE;
DROP TABLE IF EXISTS holidays CASCADE;
DROP TABLE IF EXISTS academic_years CASCADE;
DROP TABLE IF EXISTS lesson_slots CASCADE;
DROP TABLE IF EXISTS topics CASCADE;
DROP TABLE IF EXISTS book_chapters CASCADE;
DROP TABLE IF EXISTS books CASCADE;
DROP TABLE IF EXISTS custom_exam_generations CASCADE;
DROP TABLE IF EXISTS custom_lesson_plans CASCADE;
DROP TABLE IF EXISTS exam_generations CASCADE;
DROP TABLE IF EXISTS lesson_plans CASCADE;
DROP TABLE IF EXISTS teachers CASCADE;
DROP TABLE IF EXISTS clients CASCADE;
DROP TABLE IF EXISTS curriculum_subjects CASCADE;
DROP TABLE IF EXISTS curriculums CASCADE;
DROP TABLE IF EXISTS subjects CASCADE;
DROP TABLE IF EXISTS grades CASCADE;
```

**Note:** Because this drops `schema_migrations`, the runner will recreate it fresh and apply all subsequent migrations as if on a brand new database.

### DB — Migration 2: Clean Schema

File: `server/src/dars/migrations/20260513000002_init_clean.sql`

Builds the complete foundation schema:

```sql
-- Curriculums (NCP, SNC)
CREATE TABLE curriculums (
  code        TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  description TEXT
);
INSERT INTO curriculums VALUES
  ('NCP', 'National Curriculum of Pakistan', null),
  ('SNC', 'Single National Curriculum', null);

-- Clients
CREATE TABLE clients (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  api_key_hash    TEXT NOT NULL UNIQUE,
  is_active       BOOLEAN NOT NULL DEFAULT true,
  webhook_url     TEXT,
  email           TEXT UNIQUE,
  hashed_password TEXT,
  is_admin        BOOLEAN NOT NULL DEFAULT false,
  curriculum      TEXT REFERENCES curriculums(code),
  default_teacher_id UUID,           -- FK added after teachers table
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Teachers
CREATE TABLE teachers (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id  UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  name       TEXT NOT NULL,
  email      TEXT,
  phone      TEXT,
  school     TEXT,
  is_active  BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Add FK now that teachers exists
ALTER TABLE clients
  ADD CONSTRAINT clients_default_teacher_fkey
  FOREIGN KEY (default_teacher_id) REFERENCES teachers(id) ON DELETE SET NULL;

-- Webhook deliveries
CREATE TABLE webhook_deliveries (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id         UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  event             TEXT NOT NULL,
  payload           JSONB NOT NULL,
  status            TEXT NOT NULL DEFAULT 'pending',
  attempts          INT NOT NULL DEFAULT 0,
  last_attempt_at   TIMESTAMPTZ,
  next_attempt_at   TIMESTAMPTZ,
  response_status   INT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Generated lesson plans (unified, client-scoped)
CREATE TABLE generated_lesson_plans (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id         UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  external_id       TEXT,
  status            TEXT NOT NULL DEFAULT 'PENDING',
  grade             TEXT NOT NULL,
  subject           TEXT NOT NULL,
  curriculum        TEXT NOT NULL REFERENCES curriculums(code),
  topic             TEXT,
  page_number       TEXT,
  class_strength    INT,
  lp_type           TEXT,
  content           TEXT,
  content_bilingual TEXT,
  tags              JSONB NOT NULL DEFAULT '{}',
  metadata_         JSONB NOT NULL DEFAULT '{}',
  error_message     TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Generated exams (unified, client-scoped)
CREATE TABLE generated_exams (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  external_id     TEXT,
  status          TEXT NOT NULL DEFAULT 'PENDING',
  curriculum      TEXT NOT NULL REFERENCES curriculums(code),
  grade           INT NOT NULL,
  subject         TEXT NOT NULL,
  page_ranges     TEXT NOT NULL,
  generation_type TEXT NOT NULL DEFAULT 'exam',
  eg_job_id       TEXT,
  result          JSONB,
  error_message   TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Books (curriculum data bank)
CREATE TABLE books (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  core_id         INT,
  curriculum      TEXT NOT NULL REFERENCES curriculums(code),
  grade           INT NOT NULL,
  subject         TEXT NOT NULL,
  title           TEXT NOT NULL,
  publisher       TEXT,
  edition         TEXT,
  published_year  INT,
  total_chapters  INT,
  pdf_url         TEXT,
  series          TEXT,
  book_text       JSONB,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Book chapters
CREATE TABLE book_chapters (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  core_id        INT UNIQUE,
  book_id        UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  title          TEXT NOT NULL,
  chapter_number INT NOT NULL,
  start_page     INT,
  end_page       INT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Topics (within chapters)
CREATE TABLE topics (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chapter_id   UUID NOT NULL REFERENCES book_chapters(id) ON DELETE CASCADE,
  topic_number INT NOT NULL,
  title        TEXT NOT NULL,
  start_page   INT,
  end_page     INT,
  topic_text   TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Global lesson slots (curriculum data bank — one slot per teaching day per topic)
CREATE TABLE lesson_slots (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  topic_id        UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
  day_number      INT NOT NULL,
  topic_subtopic  TEXT NOT NULL,
  lesson_plan_id  UUID REFERENCES generated_lesson_plans(id) ON DELETE SET NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (topic_id, day_number)
);

-- Academic years (per client)
CREATE TABLE academic_years (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id  UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  name       TEXT NOT NULL,
  start_date DATE NOT NULL,
  end_date   DATE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT academic_years_dates_check CHECK (end_date > start_date)
);

-- Holidays (per academic year)
CREATE TABLE holidays (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id        UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  academic_year_id UUID NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
  date             DATE NOT NULL,
  name             TEXT NOT NULL
);

-- School classes (per academic year)
CREATE TABLE school_classes (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id        UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  academic_year_id UUID NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
  grade            INT NOT NULL,
  section          TEXT NOT NULL,
  name             TEXT NOT NULL,
  start_date       DATE,
  end_date         DATE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Class-subject-teacher assignments
CREATE TABLE class_subject_teachers (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id  UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  class_id   UUID NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
  subject    TEXT NOT NULL,
  teacher_id UUID REFERENCES teachers(id) ON DELETE SET NULL,
  book_id    UUID REFERENCES books(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (class_id, subject)
);

-- Weekly timetable per class-subject
CREATE TABLE timetables (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id                UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  class_subject_teacher_id UUID NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
  day_of_week              INT NOT NULL,
  start_time               TIME,
  end_time                 TIME,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Chapter plans (how many days per chapter per class-subject)
CREATE TABLE chapter_plans (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id                UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  class_subject_teacher_id UUID NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
  chapter_id               UUID NOT NULL REFERENCES book_chapters(id) ON DELETE CASCADE,
  position                 INT NOT NULL,
  teaching_days            INT NOT NULL,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (class_subject_teacher_id, chapter_id)
);

-- Per-class lesson slots (output of AI breakdown)
CREATE TABLE class_lesson_slots (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id                UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  class_subject_teacher_id UUID NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
  chapter_plan_id          UUID NOT NULL REFERENCES chapter_plans(id) ON DELETE CASCADE,
  day_number               INT NOT NULL,
  lp_type                  TEXT NOT NULL,
  title                    TEXT NOT NULL,
  lesson_plan_id           UUID REFERENCES generated_lesson_plans(id) ON DELETE SET NULL,
  status                   TEXT NOT NULL DEFAULT 'planned',
  taught_date              DATE,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Assessment slots (per class-subject)
CREATE TABLE assessment_slots (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id                UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  class_subject_teacher_id UUID NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
  chapter_plan_id          UUID REFERENCES chapter_plans(id) ON DELETE SET NULL,
  assessment_type          TEXT NOT NULL,
  scheduled_date           DATE NOT NULL,
  title                    TEXT,
  exam_id                  UUID REFERENCES generated_exams(id) ON DELETE SET NULL,
  status                   TEXT NOT NULL DEFAULT 'scheduled',
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_generated_lesson_plans_client ON generated_lesson_plans(client_id);
CREATE INDEX idx_generated_exams_client ON generated_exams(client_id);
CREATE INDEX idx_books_curriculum ON books(curriculum);
CREATE INDEX idx_class_lesson_slots_chapter_plan ON class_lesson_slots(chapter_plan_id);
CREATE INDEX idx_assessment_slots_chapter_plan ON assessment_slots(chapter_plan_id);
```

### Backend — delete these modules entirely

- `server/src/dars/lesson_plans/`
- `server/src/dars/custom_lesson_plans/`
- `server/src/dars/exam_generations/`
- `server/src/dars/custom_exam_generations/`
- `server/src/dars/assessments/`
- `server/src/dars/student_assessments/`

### Backend — new module: `generated_lps/`

Model: `GeneratedLP` → table `generated_lesson_plans` (schema above)

Endpoints:
- `POST /api/v1/lesson-plans` — queue generation (202), fires background task to LP Assistant
- `GET  /api/v1/lesson-plans` — list (filtered by client_id, paginated)
- `GET  /api/v1/lesson-plans/{id}` — get single (client_id check)

### Backend — new module: `generated_exams/`

Model: `GeneratedExam` → table `generated_exams` (schema above)

Endpoints:
- `POST /api/v1/exams` — queue generation (202), fires background task to EG
- `GET  /api/v1/exams` — list (filtered by client_id, paginated)
- `GET  /api/v1/exams/{id}` — get single (client_id check)

### Backend — update `clients/` model

Remove: `curriculum` (old string column), `supabase_user_id`
Add: `curriculum TEXT FK → curriculums`

### Backend — update `auth/`

- `POST /auth/signup` — add required `curriculum` field (NCP or SNC), auto-create default teacher after client creation
- `GET /api/v1/me` — return `curriculum` as `{code, name}` object
- `PATCH /api/v1/me` — `curriculum` is immutable; only `webhook_url` updatable

### Backend — update `main.py`

Remove routers: `lesson_plans`, `exam_generations`, `assessments`, `student_assessments`, `custom_lesson_plans`, `custom_exam_generations`

Add routers: `generated_lps`, `generated_exams`

### Backend — update `curriculum/` module

- `assessment_id` field removed from `CurriculumLesson` schema (assessments module gone)
- `lesson_plan_id` on `lesson_slots` now references `generated_lesson_plans`
- `LessonSlot` model updated to FK `generated_lesson_plans`

### Backend — update `school/` module

- `AssessmentSlot.exam_generation_id` → renamed to `exam_id`, now proper FK to `generated_exams`
- `ClassLessonSlot.lesson_plan_id` → proper FK to `generated_lesson_plans`

### Tests

`server/tests/test_generated_lps.py`:
- Create LP → status=PENDING
- Get by id (client isolation)
- List filtered by client
- Wrong client → 403

`server/tests/test_generated_exams.py`:
- Same pattern

`server/tests/test_auth.py` (update):
- Signup NCP → api_key returned, default teacher created
- Signup SNC → api_key returned
- Signup without curriculum → 422
- `GET /api/v1/me` → returns `{curriculum: {code, name}}`

### Frontend

- `webapp/app/dashboard/lesson-plans/page.tsx` — update calls: `custom-lesson-plans` → `lesson-plans`
- `webapp/app/dashboard/exam-generator/page.tsx` — update calls: `custom-exam-generations` → `exams`
- `webapp/app/dashboard/settings/page.tsx` — curriculum dropdown → read-only display
- Add signup page with curriculum selector: `webapp/app/dashboard/signup/page.tsx`

## Bead

- ID: `feat-step1-foundation`
- Title: Step 1 — Foundation cleanup + clean slate DB
- Category: feature

### DB — delete old migration files

Delete everything in `server/src/dars/migrations/` except the two new files:
- Keep: `20260513000001_reset.sql`
- Keep: `20260513000002_init_clean.sql`
- Delete: all other `.sql` files (they are superseded by the clean init)

## Risks & constraints

- The reset migration drops `schema_migrations` itself — the runner will recreate it and apply all migrations fresh. This is intentional.
- Run this against staging first, verify everything comes up clean before touching prod.
- `lesson_slots.lesson_plan_id` previously pointed to old `lesson_plans` table — now points to `generated_lesson_plans`. The clean slate handles this automatically.
- `assessment_slots.exam_generation_id` renamed to `exam_id` — update all references in `school/` module.
- Tests use SQLite — `JSONB` → use `JSON` type in SQLAlchemy models (`sqlalchemy.types.JSON`), not PG-specific `JSONB`.

## E2E test scenarios

1. Run migrations on fresh DB → all tables created, no errors
2. Signup with NCP → api_key returned → `GET /api/v1/me` returns `curriculum: {code: "NCP", name: "National Curriculum of Pakistan"}`
3. Default teacher auto-created on signup → `client.default_teacher_id` set
4. `POST /api/v1/lesson-plans` → 202 → poll → READY
5. `GET /api/v1/lesson-plans` → only client's own LPs
6. `POST /api/v1/exams` → 202 → poll → READY
7. Old routes (`/custom-lesson-plans`, `/custom-exam-generations`) → 404
8. Signup without curriculum → 422
