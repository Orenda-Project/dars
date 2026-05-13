-- Clean init: drop everything, rebuild with standard columns on every table.
-- Standard columns on every table: id BIGSERIAL PK, uuid UUID UNIQUE, created_at, updated_at, deleted_at.
-- FKs always reference id (integer). uuid is for cross-environment data migration only.

-- Drop all tables
DROP TABLE IF EXISTS assessment_slots CASCADE;
DROP TABLE IF EXISTS class_lesson_slots CASCADE;
DROP TABLE IF EXISTS chapter_plans CASCADE;
DROP TABLE IF EXISTS timetables CASCADE;
DROP TABLE IF EXISTS class_subject_teachers CASCADE;
DROP TABLE IF EXISTS school_classes CASCADE;
DROP TABLE IF EXISTS holidays CASCADE;
DROP TABLE IF EXISTS academic_years CASCADE;
DROP TABLE IF EXISTS lesson_slots CASCADE;
DROP TABLE IF EXISTS topic_slos CASCADE;
DROP TABLE IF EXISTS topics CASCADE;
DROP TABLE IF EXISTS book_chapters CASCADE;
DROP TABLE IF EXISTS curriculum_chapter_schedule CASCADE;
DROP TABLE IF EXISTS books CASCADE;
DROP TABLE IF EXISTS slos CASCADE;
DROP TABLE IF EXISTS generated_lesson_plans CASCADE;
DROP TABLE IF EXISTS generated_exams CASCADE;
DROP TABLE IF EXISTS webhook_deliveries CASCADE;
DROP TABLE IF EXISTS teachers CASCADE;
DROP TABLE IF EXISTS clients CASCADE;
DROP TABLE IF EXISTS grades CASCADE;
DROP TABLE IF EXISTS subjects CASCADE;
DROP TABLE IF EXISTS curriculums CASCADE;
DROP TABLE IF EXISTS schema_migrations CASCADE;

-- Recreate schema_migrations
CREATE TABLE schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- curriculums
CREATE TABLE curriculums (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

-- grades
CREATE TABLE grades (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    code INTEGER NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

-- subjects
CREATE TABLE subjects (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

-- clients
CREATE TABLE clients (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    api_key_hash VARCHAR(64) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT true,
    webhook_url VARCHAR(500),
    email VARCHAR(255) UNIQUE,
    hashed_password VARCHAR(255),
    is_admin BOOLEAN NOT NULL DEFAULT false,
    curriculum TEXT,
    default_teacher_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

-- teachers
CREATE TABLE teachers (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    school VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

-- slos
CREATE TABLE slos (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    curriculum TEXT NOT NULL,
    grade INTEGER NOT NULL,
    subject TEXT NOT NULL,
    code TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_slos_curriculum_grade_subject ON slos(curriculum, grade, subject);

-- books
CREATE TABLE books (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    core_id INTEGER,
    curriculum TEXT NOT NULL,
    grade INTEGER NOT NULL,
    subject TEXT NOT NULL,
    title TEXT NOT NULL,
    publisher TEXT,
    edition TEXT,
    published_year INTEGER,
    total_chapters INTEGER,
    pdf_url TEXT,
    series TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

-- book_chapters
CREATE TABLE book_chapters (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    core_id INTEGER UNIQUE,
    book_id BIGINT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    chapter_number INTEGER NOT NULL,
    start_page INTEGER,
    end_page INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

-- topics
CREATE TABLE topics (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    chapter_id BIGINT NOT NULL REFERENCES book_chapters(id) ON DELETE CASCADE,
    topic_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    start_page INTEGER,
    end_page INTEGER,
    topic_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

-- topic_slos
CREATE TABLE topic_slos (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    topic_id BIGINT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    slo_id BIGINT NOT NULL REFERENCES slos(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT uq_topic_slo UNIQUE (topic_id, slo_id)
);
CREATE INDEX idx_topic_slos_topic ON topic_slos(topic_id);

-- curriculum_chapter_schedule
CREATE TABLE curriculum_chapter_schedule (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    curriculum TEXT NOT NULL,
    book_id BIGINT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    chapter_id BIGINT NOT NULL REFERENCES book_chapters(id) ON DELETE CASCADE,
    suggested_teaching_days INTEGER NOT NULL,
    suggested_position INTEGER NOT NULL,
    term TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT uq_ccs_curriculum_chapter UNIQUE (curriculum, chapter_id)
);

-- lesson_slots
CREATE TABLE lesson_slots (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    topic_id BIGINT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    day_number INTEGER NOT NULL,
    scheduled_date TEXT,
    topic_subtopic TEXT NOT NULL,
    lesson_plan_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

-- generated_lesson_plans
CREATE TABLE generated_lesson_plans (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    external_id TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    grade VARCHAR(50) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    curriculum VARCHAR(50) NOT NULL,
    topic TEXT,
    page_number VARCHAR(50),
    class_strength INTEGER,
    lp_type VARCHAR(100),
    content TEXT,
    content_bilingual TEXT,
    tags JSONB NOT NULL DEFAULT '{}',
    metadata_ JSONB NOT NULL DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

-- generated_exams
CREATE TABLE generated_exams (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    external_id TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    curriculum VARCHAR(50) NOT NULL,
    grade INTEGER NOT NULL,
    subject VARCHAR(255) NOT NULL,
    page_ranges TEXT NOT NULL,
    generation_type VARCHAR(50) NOT NULL DEFAULT 'exam',
    eg_job_id TEXT,
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

-- webhook_deliveries
CREATE TABLE webhook_deliveries (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    lesson_plan_id BIGINT NOT NULL,
    event VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    next_attempt_at TIMESTAMPTZ,
    response_status INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

-- academic_years
CREATE TABLE academic_years (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT academic_years_dates_check CHECK (end_date > start_date)
);

-- holidays
CREATE TABLE holidays (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    academic_year_id BIGINT NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

-- school_classes
CREATE TABLE school_classes (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    academic_year_id BIGINT NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    grade INTEGER NOT NULL,
    section TEXT NOT NULL,
    name TEXT NOT NULL,
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

-- class_subject_teachers
CREATE TABLE class_subject_teachers (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    class_id BIGINT NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    teacher_id BIGINT REFERENCES teachers(id) ON DELETE SET NULL,
    book_id BIGINT REFERENCES books(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT uq_cst_class_subject UNIQUE (class_id, subject)
);

-- timetables
CREATE TABLE timetables (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    class_subject_teacher_id BIGINT NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL,
    start_time TIME,
    end_time TIME,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

-- chapter_plans
CREATE TABLE chapter_plans (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    class_subject_teacher_id BIGINT NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    chapter_id BIGINT NOT NULL REFERENCES book_chapters(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    teaching_days INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT uq_chapter_plan_cst_chapter UNIQUE (class_subject_teacher_id, chapter_id)
);

-- class_lesson_slots
CREATE TABLE class_lesson_slots (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    class_subject_teacher_id BIGINT NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    chapter_plan_id BIGINT NOT NULL REFERENCES chapter_plans(id) ON DELETE CASCADE,
    day_number INTEGER NOT NULL,
    lp_type TEXT NOT NULL,
    title TEXT NOT NULL,
    lesson_plan_id BIGINT REFERENCES generated_lesson_plans(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    taught_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_class_lesson_slots_chapter_plan ON class_lesson_slots(chapter_plan_id);

-- assessment_slots
CREATE TABLE assessment_slots (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    class_subject_teacher_id BIGINT NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    chapter_plan_id BIGINT REFERENCES chapter_plans(id) ON DELETE SET NULL,
    assessment_type TEXT NOT NULL,
    scheduled_date DATE NOT NULL,
    title TEXT,
    exam_id BIGINT REFERENCES generated_exams(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX idx_assessment_slots_chapter_plan ON assessment_slots(chapter_plan_id);

-- Seed reference data
INSERT INTO curriculums (code, name, description) VALUES
    ('NCP', 'National Curriculum of Pakistan', 'Pre-2006 national curriculum'),
    ('SNC', 'Single National Curriculum', 'Unified curriculum introduced 2020');

INSERT INTO grades (code, display_name) VALUES
    (1, 'Grade 1'), (2, 'Grade 2'), (3, 'Grade 3'), (4, 'Grade 4'),
    (5, 'Grade 5'), (6, 'Grade 6'), (7, 'Grade 7'), (8, 'Grade 8'),
    (9, 'Grade 9'), (10, 'Grade 10'), (11, 'Grade 11'), (12, 'Grade 12');

INSERT INTO subjects (code, display_name) VALUES
    ('english', 'English'),
    ('urdu', 'Urdu'),
    ('math', 'Mathematics'),
    ('science', 'Science'),
    ('social_studies', 'Social Studies'),
    ('islamiat', 'Islamiat'),
    ('computer', 'Computer Science');
