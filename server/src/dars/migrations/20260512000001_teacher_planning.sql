-- Teacher Planning Tool: academic years, holidays, classes, timetables,
-- chapter plans, lesson slots, and assessment slots.

-- teachers was dropped in the init migration; recreate it if absent
CREATE TABLE IF NOT EXISTS teachers (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id  UUID        NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name       TEXT        NOT NULL,
    email      TEXT,
    phone      TEXT,
    school     TEXT,
    is_active  BOOLEAN     NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS academic_years (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id        UUID        NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name             TEXT        NOT NULL,
    start_date       DATE        NOT NULL,
    end_date         DATE        NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS holidays (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id        UUID        NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    academic_year_id UUID        NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    date             DATE        NOT NULL,
    name             TEXT        NOT NULL
);

CREATE TABLE IF NOT EXISTS school_classes (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id        UUID        NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    academic_year_id UUID        NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    grade            INT         NOT NULL,
    section          TEXT        NOT NULL,
    name             TEXT        NOT NULL,
    start_date       DATE,
    end_date         DATE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS class_subject_teachers (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id   UUID        NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    class_id    UUID        NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
    subject     TEXT        NOT NULL,
    teacher_id  UUID        REFERENCES teachers(id) ON DELETE SET NULL,
    book_id     UUID        REFERENCES books(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (class_id, subject)
);

CREATE TABLE IF NOT EXISTS timetables (
    id                       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id                UUID        NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    class_subject_teacher_id UUID        NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    day_of_week              INT         NOT NULL,  -- 0=Mon ... 6=Sun
    start_time               TIME,
    end_time                 TIME,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chapter_plans (
    id                       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id                UUID        NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    class_subject_teacher_id UUID        NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    chapter_id               UUID        NOT NULL REFERENCES book_chapters(id) ON DELETE CASCADE,
    position                 INT         NOT NULL,
    teaching_days            INT         NOT NULL,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (class_subject_teacher_id, chapter_id)
);

CREATE TABLE IF NOT EXISTS class_lesson_slots (
    id                       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id                UUID        NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    class_subject_teacher_id UUID        NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    chapter_plan_id          UUID        NOT NULL REFERENCES chapter_plans(id) ON DELETE CASCADE,
    day_number               INT         NOT NULL,
    lp_type                  TEXT        NOT NULL,
    title                    TEXT        NOT NULL,
    lesson_plan_id           UUID        REFERENCES lesson_plans(id) ON DELETE SET NULL,
    status                   TEXT        NOT NULL DEFAULT 'planned',
    taught_date              DATE,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS assessment_slots (
    id                       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id                UUID        NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    class_subject_teacher_id UUID        NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    chapter_plan_id          UUID        REFERENCES chapter_plans(id) ON DELETE SET NULL,
    assessment_type          TEXT        NOT NULL,  -- formative | summative
    scheduled_date           DATE        NOT NULL,
    title                    TEXT,
    exam_generation_id       UUID,
    status                   TEXT        NOT NULL DEFAULT 'scheduled',
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
