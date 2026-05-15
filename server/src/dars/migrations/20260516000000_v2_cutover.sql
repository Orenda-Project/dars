-- v2 cutover migration: drop everything, recreate under v2 schema.
-- Plan: docs/plans/2026-05-15-dars-v2-rebuild/02-data-model.md
-- All PKs are UUID (D-decision from 2026-05-15 Phase 1 kickoff; supersedes earlier BIGSERIAL+UUID pattern).

-- ---------------------------------------------------------------------------
-- Clean slate
-- ---------------------------------------------------------------------------
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- for gen_random_uuid()

CREATE TABLE schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===========================================================================
-- SECTION 1: Lookup tables (no FKs; seeded by v2_seed.py)
-- ===========================================================================

CREATE TABLE grades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code INT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE subjects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE curriculums (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===========================================================================
-- SECTION 2: Curriculum-level outcomes
-- ===========================================================================

CREATE TABLE slos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id UUID NOT NULL REFERENCES curriculums(id) ON DELETE CASCADE,
    grade_id UUID NOT NULL REFERENCES grades(id),
    subject_id UUID NOT NULL REFERENCES subjects(id),
    code TEXT NOT NULL,
    statement TEXT NOT NULL,
    domain TEXT,
    position INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (curriculum_id, grade_id, subject_id, code)
);
CREATE INDEX idx_slos_lookup ON slos(curriculum_id, grade_id, subject_id);

CREATE TABLE sub_slos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slo_id UUID NOT NULL REFERENCES slos(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    statement TEXT NOT NULL,
    position INT NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'manual',  -- 'manual' | 'schema_breakdown'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (slo_id, code)
);
CREATE INDEX idx_sub_slos_slo ON sub_slos(slo_id);

-- ===========================================================================
-- SECTION 3: Books, chapters, topics
-- ===========================================================================

CREATE TABLE books (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id UUID NOT NULL REFERENCES curriculums(id),
    grade_id UUID NOT NULL REFERENCES grades(id),
    subject_id UUID NOT NULL REFERENCES subjects(id),
    title TEXT NOT NULL,
    publisher TEXT,
    edition TEXT,
    published_year INT,
    total_chapters INT,
    pdf_url TEXT,
    book_text JSONB,  -- [{pdf_page_no: int, text: str}, ...]
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_books_lookup ON books(curriculum_id, grade_id, subject_id);

CREATE TABLE book_chapters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_id UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    chapter_number INT NOT NULL,
    title TEXT NOT NULL,
    start_page INT,
    end_page INT,
    chapter_text JSONB,  -- OCR slice for this chapter
    status TEXT NOT NULL DEFAULT 'draft',  -- 'draft' | 'published'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (book_id, chapter_number)
);
CREATE INDEX idx_book_chapters_book ON book_chapters(book_id);

CREATE TABLE topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_chapter_id UUID NOT NULL REFERENCES book_chapters(id) ON DELETE CASCADE,
    topic_number INT NOT NULL,
    title TEXT NOT NULL,
    start_line INT,
    end_line INT,
    topic_text TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (book_chapter_id, topic_number)
);
CREATE INDEX idx_topics_chapter ON topics(book_chapter_id);

CREATE TABLE book_chapter_slos (
    book_chapter_id UUID NOT NULL REFERENCES book_chapters(id) ON DELETE CASCADE,
    slo_id UUID NOT NULL REFERENCES slos(id) ON DELETE CASCADE,
    PRIMARY KEY (book_chapter_id, slo_id)
);

CREATE TABLE topic_sub_slos (
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    sub_slo_id UUID NOT NULL REFERENCES sub_slos(id) ON DELETE CASCADE,
    PRIMARY KEY (topic_id, sub_slo_id)
);

-- ===========================================================================
-- SECTION 4: Tenancy
-- ===========================================================================

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    curriculum_id UUID NOT NULL REFERENCES curriculums(id),
    api_key_hash TEXT NOT NULL,
    api_key_prefix TEXT NOT NULL,  -- first 8 chars of raw key for display
    default_teacher_id UUID,        -- FK added later (circular with teachers.org_id)
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_organizations_api_key_hash ON organizations(api_key_hash);

CREATE TABLE org_admins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE schools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_schools_org ON schools(org_id);

CREATE TABLE teachers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_teachers_school ON teachers(school_id);

-- Now we can add the deferred FK from organizations.default_teacher_id
ALTER TABLE organizations
    ADD CONSTRAINT organizations_default_teacher_fk
    FOREIGN KEY (default_teacher_id) REFERENCES teachers(id) ON DELETE SET NULL;

CREATE TABLE academic_years (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_academic_years_school ON academic_years(school_id);

CREATE TABLE school_classes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    academic_year_id UUID NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    grade_id UUID NOT NULL REFERENCES grades(id),
    section TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_school_classes_ay ON school_classes(academic_year_id);

CREATE TABLE class_subject_teachers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    school_class_id UUID NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
    subject_id UUID NOT NULL REFERENCES subjects(id),
    teacher_id UUID REFERENCES teachers(id) ON DELETE SET NULL,
    book_id UUID REFERENCES books(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (school_class_id, subject_id)
);
CREATE INDEX idx_cst_teacher ON class_subject_teachers(teacher_id);
CREATE INDEX idx_cst_org ON class_subject_teachers(org_id);

CREATE TABLE cst_state (
    cst_id UUID PRIMARY KEY REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    current_sequence_position INT NOT NULL DEFAULT 1,
    joined_at_position INT NOT NULL DEFAULT 1,
    last_marked_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===========================================================================
-- SECTION 5: Holidays + Timetable
-- ===========================================================================

CREATE TABLE org_holidays (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    academic_year_id UUID NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_org_holidays_ay ON org_holidays(academic_year_id);

CREATE TABLE school_holiday_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    name TEXT,
    action TEXT NOT NULL CHECK (action IN ('add', 'remove')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_school_holiday_overrides_school ON school_holiday_overrides(school_id);

CREATE TABLE cst_holiday_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cst_id UUID NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    name TEXT,
    action TEXT NOT NULL CHECK (action IN ('add', 'remove')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_cst_holiday_overrides_cst ON cst_holiday_overrides(cst_id);

CREATE TABLE timetables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cst_id UUID NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    day_of_week INT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),  -- 0=Mon, default Mon-Fri (0..4)
    start_time TIME,
    end_time TIME,
    UNIQUE (cst_id, day_of_week)
);

-- ===========================================================================
-- SECTION 6: Breakdown (plan model)
-- ===========================================================================

CREATE TABLE breakdowns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope TEXT NOT NULL CHECK (scope IN ('global', 'org', 'class')),
    scope_ref_id UUID,  -- NULL for global; org_id for org; cst_id for class
    curriculum_id UUID NOT NULL REFERENCES curriculums(id),
    grade_id UUID NOT NULL REFERENCES grades(id),
    subject_id UUID NOT NULL REFERENCES subjects(id),
    book_id UUID REFERENCES books(id) ON DELETE SET NULL,
    parent_breakdown_id UUID REFERENCES breakdowns(id) ON DELETE SET NULL,
    previous_version_id UUID REFERENCES breakdowns(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'deleted')),
    total_teaching_days INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_breakdowns_lookup ON breakdowns(scope, scope_ref_id, curriculum_id, grade_id, subject_id, status);

CREATE TABLE breakdown_chapters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    breakdown_id UUID NOT NULL REFERENCES breakdowns(id) ON DELETE CASCADE,
    book_chapter_id UUID NOT NULL REFERENCES book_chapters(id),
    position INT NOT NULL,
    teaching_days INT NOT NULL,
    UNIQUE (breakdown_id, position)
);

CREATE TABLE breakdown_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    breakdown_id UUID NOT NULL REFERENCES breakdowns(id) ON DELETE CASCADE,
    breakdown_chapter_id UUID NOT NULL REFERENCES breakdown_chapters(id) ON DELETE CASCADE,
    position INT NOT NULL,           -- global sequence position 1..N across breakdown
    chapter_position INT NOT NULL,   -- position within chapter
    slot_type TEXT NOT NULL CHECK (slot_type IN ('lesson', 'formative_assessment', 'summative_assessment', 'revision')),
    lp_type TEXT,
    topic_id UUID REFERENCES topics(id) ON DELETE SET NULL,
    anchor_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (breakdown_id, position)
);
CREATE INDEX idx_breakdown_slots_chapter ON breakdown_slots(breakdown_chapter_id);

CREATE TABLE breakdown_slot_topics (
    breakdown_slot_id UUID NOT NULL REFERENCES breakdown_slots(id) ON DELETE CASCADE,
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    position INT NOT NULL,
    PRIMARY KEY (breakdown_slot_id, topic_id)
);

-- ===========================================================================
-- SECTION 7: Realized slots (per CST) + progress
-- ===========================================================================

CREATE TABLE class_lesson_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    cst_id UUID NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    breakdown_slot_id UUID NOT NULL REFERENCES breakdown_slots(id) ON DELETE CASCADE,
    position INT NOT NULL,
    slot_type TEXT NOT NULL,
    lp_type TEXT,
    topic_id UUID REFERENCES topics(id) ON DELETE SET NULL,
    anchor_date DATE,
    generated_lp_id UUID,  -- FK added after generated_lps is created
    status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'taught', 'skipped')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cst_id, position)
);
CREATE INDEX idx_class_lesson_slots_status ON class_lesson_slots(cst_id, status);

CREATE TABLE class_assessment_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    cst_id UUID NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    breakdown_slot_id UUID NOT NULL REFERENCES breakdown_slots(id) ON DELETE CASCADE,
    position INT NOT NULL,
    assessment_type TEXT NOT NULL CHECK (assessment_type IN ('formative', 'summative')),
    anchor_date DATE,
    generated_exam_id UUID,  -- FK added after generated_exams
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'skipped')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cst_id, position)
);

CREATE TABLE class_assessment_slot_topics (
    class_assessment_slot_id UUID NOT NULL REFERENCES class_assessment_slots(id) ON DELETE CASCADE,
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    position INT NOT NULL,
    PRIMARY KEY (class_assessment_slot_id, topic_id)
);

CREATE TABLE slot_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cst_id UUID NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    slot_kind TEXT NOT NULL CHECK (slot_kind IN ('lesson', 'assessment')),
    slot_id UUID NOT NULL,  -- references either class_lesson_slots or class_assessment_slots (no FK; polymorphic)
    action TEXT NOT NULL CHECK (action IN ('taught', 'skipped', 'completed')),
    occurred_on DATE NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes TEXT
);
CREATE INDEX idx_slot_progress_slot ON slot_progress(cst_id, slot_kind, slot_id);
CREATE INDEX idx_slot_progress_date ON slot_progress(cst_id, occurred_on);

CREATE TABLE cst_sub_slo_coverage (
    cst_id UUID NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    sub_slo_id UUID NOT NULL REFERENCES sub_slos(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('taught', 'not_taught')),
    marked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (cst_id, sub_slo_id)
);

-- ===========================================================================
-- SECTION 8: Generation (LP / Exam) + cost tracking
-- ===========================================================================

CREATE TABLE generated_lps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key TEXT,  -- NULL for class-scope LPs only; UNIQUE among global per partial index below
    scope TEXT NOT NULL CHECK (scope IN ('global', 'class')),
    scope_ref_id UUID,  -- NULL for global, cst_id for class-scoped
    curriculum_id UUID NOT NULL REFERENCES curriculums(id),
    grade_id UUID NOT NULL REFERENCES grades(id),
    subject_id UUID NOT NULL REFERENCES subjects(id),
    topic_id UUID REFERENCES topics(id) ON DELETE SET NULL,
    revision_topic_set_hash TEXT,
    lp_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'IN_FLIGHT', 'READY', 'ERROR')),
    job_id TEXT,
    content TEXT,
    content_bilingual TEXT,
    covered_sub_slo_ids UUID[],
    tagging_status TEXT NOT NULL DEFAULT 'pending' CHECK (tagging_status IN ('pending', 'done', 'failed')),
    cost_usd NUMERIC,
    tokens_input INT,
    tokens_output INT,
    model TEXT,
    error_message TEXT,
    lp_assistant_response_raw JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_generated_lps_cache_key ON generated_lps(cache_key) WHERE scope = 'global';
CREATE INDEX idx_generated_lps_status ON generated_lps(status);
CREATE INDEX idx_generated_lps_scope ON generated_lps(scope, scope_ref_id);

CREATE TABLE generated_exams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key TEXT,
    scope TEXT NOT NULL CHECK (scope IN ('global', 'class')),
    scope_ref_id UUID,
    curriculum_id UUID NOT NULL REFERENCES curriculums(id),
    grade_id UUID NOT NULL REFERENCES grades(id),
    subject_id UUID NOT NULL REFERENCES subjects(id),
    topic_ids_hash TEXT NOT NULL,
    generation_type TEXT NOT NULL,
    question_config_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'IN_FLIGHT', 'READY', 'ERROR')),
    job_id TEXT,
    result JSONB,
    exam_paper_html TEXT,
    question_sub_slo_tags JSONB,
    tagging_status TEXT NOT NULL DEFAULT 'pending' CHECK (tagging_status IN ('pending', 'done', 'failed')),
    cost_usd NUMERIC,
    tokens_input INT,
    tokens_output INT,
    model TEXT,
    error_message TEXT,
    ug_eg_response_raw JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_generated_exams_cache_key ON generated_exams(cache_key) WHERE scope = 'global';
CREATE INDEX idx_generated_exams_status ON generated_exams(status);

-- Now add the deferred FKs back to class slots
ALTER TABLE class_lesson_slots
    ADD CONSTRAINT class_lesson_slots_generated_lp_fk
    FOREIGN KEY (generated_lp_id) REFERENCES generated_lps(id) ON DELETE SET NULL;

ALTER TABLE class_assessment_slots
    ADD CONSTRAINT class_assessment_slots_generated_exam_fk
    FOREIGN KEY (generated_exam_id) REFERENCES generated_exams(id) ON DELETE SET NULL;

-- ===========================================================================
-- SECTION 9: Exam results + mastery
-- ===========================================================================

CREATE TABLE exam_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_assessment_slot_id UUID NOT NULL REFERENCES class_assessment_slots(id) ON DELETE CASCADE,
    students_present INT NOT NULL,
    recorded_by_teacher_id UUID REFERENCES teachers(id) ON DELETE SET NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_exam_results_slot ON exam_results(class_assessment_slot_id);

CREATE TABLE exam_question_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_result_id UUID NOT NULL REFERENCES exam_results(id) ON DELETE CASCADE,
    question_index INT NOT NULL,
    sub_slo_id UUID REFERENCES sub_slos(id) ON DELETE SET NULL,
    students_correct INT NOT NULL,
    marks_total INT NOT NULL,
    marks_earned_avg NUMERIC
);

CREATE TABLE sub_slo_mastery (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cst_id UUID NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    sub_slo_id UUID NOT NULL REFERENCES sub_slos(id) ON DELETE CASCADE,
    class_assessment_slot_id UUID NOT NULL REFERENCES class_assessment_slots(id) ON DELETE CASCADE,
    mastery_percent NUMERIC NOT NULL,
    assessed_on DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sub_slo_mastery_lookup ON sub_slo_mastery(cst_id, sub_slo_id, assessed_on);

-- ===========================================================================
-- SECTION 10: Webhooks audit
-- ===========================================================================

CREATE TABLE webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL CHECK (source IN ('lp_assistant', 'ug_eg')),
    job_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_webhook_events_job ON webhook_events(source, job_id);
