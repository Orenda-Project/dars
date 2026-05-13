-- Curriculums (NCP, SNC)
CREATE TABLE IF NOT EXISTS curriculums (
  code        TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  description TEXT
);
INSERT INTO curriculums VALUES
  ('NCP', 'National Curriculum of Pakistan', null),
  ('SNC', 'Single National Curriculum', null)
ON CONFLICT (code) DO NOTHING;

-- Clients
CREATE TABLE IF NOT EXISTS clients (
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
CREATE TABLE IF NOT EXISTS teachers (
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

-- Add FK now that teachers exists (idempotent)
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'clients_default_teacher_fkey'
  ) THEN
    ALTER TABLE clients
      ADD CONSTRAINT clients_default_teacher_fkey
      FOREIGN KEY (default_teacher_id) REFERENCES teachers(id) ON DELETE SET NULL;
  END IF;
END $$;

-- Webhook deliveries
CREATE TABLE IF NOT EXISTS webhook_deliveries (
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
CREATE TABLE IF NOT EXISTS generated_lesson_plans (
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
CREATE TABLE IF NOT EXISTS generated_exams (
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
CREATE TABLE IF NOT EXISTS books (
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
CREATE TABLE IF NOT EXISTS book_chapters (
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
CREATE TABLE IF NOT EXISTS topics (
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
CREATE TABLE IF NOT EXISTS lesson_slots (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  topic_id        UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
  day_number      INT NOT NULL,
  topic_subtopic  TEXT NOT NULL,
  lesson_plan_id  UUID REFERENCES generated_lesson_plans(id) ON DELETE SET NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (topic_id, day_number)
);

-- Academic years (per client)
CREATE TABLE IF NOT EXISTS academic_years (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id  UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  name       TEXT NOT NULL,
  start_date DATE NOT NULL,
  end_date   DATE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT academic_years_dates_check CHECK (end_date > start_date)
);

-- Holidays (per academic year)
CREATE TABLE IF NOT EXISTS holidays (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id        UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  academic_year_id UUID NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
  date             DATE NOT NULL,
  name             TEXT NOT NULL
);

-- School classes (per academic year)
CREATE TABLE IF NOT EXISTS school_classes (
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
CREATE TABLE IF NOT EXISTS class_subject_teachers (
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
CREATE TABLE IF NOT EXISTS timetables (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id                UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  class_subject_teacher_id UUID NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
  day_of_week              INT NOT NULL,
  start_time               TIME,
  end_time                 TIME,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Chapter plans (how many days per chapter per class-subject)
CREATE TABLE IF NOT EXISTS chapter_plans (
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
CREATE TABLE IF NOT EXISTS class_lesson_slots (
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
CREATE TABLE IF NOT EXISTS assessment_slots (
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
CREATE INDEX IF NOT EXISTS idx_generated_lesson_plans_client ON generated_lesson_plans(client_id);
CREATE INDEX IF NOT EXISTS idx_generated_exams_client ON generated_exams(client_id);
CREATE INDEX IF NOT EXISTS idx_books_curriculum ON books(curriculum);
CREATE INDEX IF NOT EXISTS idx_class_lesson_slots_chapter_plan ON class_lesson_slots(chapter_plan_id);
CREATE INDEX IF NOT EXISTS idx_assessment_slots_chapter_plan ON assessment_slots(chapter_plan_id);
