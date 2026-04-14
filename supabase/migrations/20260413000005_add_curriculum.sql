-- Migration: add curriculum tables
-- grades, subjects, slo_providers, slos, curriculums, curriculum_grade_subjects, curriculum_days, curriculum_day_slos, client_curriculums

CREATE TABLE grades (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    label varchar(50) NOT NULL,
    short_code varchar(10) NOT NULL UNIQUE,
    order_index int NOT NULL
);

CREATE TABLE subjects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    label varchar(100) NOT NULL,
    short_code varchar(20) NOT NULL UNIQUE
);

-- SLO providers: NCP (national), SNC (Punjab), etc.
CREATE TABLE slo_providers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug varchar(50) NOT NULL UNIQUE,   -- e.g. 'ncp', 'snc_punjab'
    name varchar(255) NOT NULL,          -- e.g. 'National Curriculum of Pakistan (NCP)'
    issuing_body varchar(255) NOT NULL,  -- e.g. 'Federal Government of Pakistan'
    description text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE slos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id uuid NOT NULL REFERENCES slo_providers(id),
    code varchar(50) NOT NULL,
    statement text NOT NULL DEFAULT '',
    subject_id uuid NOT NULL REFERENCES subjects(id),
    grade_id uuid NOT NULL REFERENCES grades(id),
    domain varchar(100),
    language_skills text[],
    sub_strand text,
    source_id int,            -- original PK from taleemabad-core for traceability
    is_active boolean NOT NULL DEFAULT true,
    UNIQUE(provider_id, code, grade_id, subject_id)
);
CREATE INDEX ON slos(provider_id);
CREATE INDEX ON slos(grade_id, subject_id);

CREATE TABLE curriculums (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(255) NOT NULL,
    board varchar(50) NOT NULL,
    academic_year varchar(20),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE curriculum_grade_subjects (
    curriculum_id uuid NOT NULL REFERENCES curriculums(id) ON DELETE CASCADE,
    grade_id uuid NOT NULL REFERENCES grades(id),
    subject_id uuid NOT NULL REFERENCES subjects(id),
    PRIMARY KEY (curriculum_id, grade_id, subject_id)
);

CREATE TABLE curriculum_days (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id uuid NOT NULL REFERENCES curriculums(id) ON DELETE CASCADE,
    grade_id uuid NOT NULL REFERENCES grades(id),
    subject_id uuid NOT NULL REFERENCES subjects(id),
    book_id int REFERENCES books(id),
    chapter_number int NOT NULL,
    chapter_title text NOT NULL,
    sequence int NOT NULL,
    day_label varchar(100),
    day_number int,
    segment_type varchar(30) NOT NULL DEFAULT 'lesson',
    topic text NOT NULL,
    skill_type varchar(50),
    cpa_phase varchar(50),
    pages varchar(50),
    blooms_level varchar(30),
    duration_minutes int,
    slide_count int,
    is_enriched boolean NOT NULL DEFAULT false,
    is_verified boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON curriculum_days(curriculum_id, grade_id, subject_id);
CREATE INDEX ON curriculum_days(sequence);

CREATE TABLE curriculum_day_slos (
    curriculum_day_id uuid NOT NULL REFERENCES curriculum_days(id) ON DELETE CASCADE,
    slo_id uuid NOT NULL REFERENCES slos(id),
    PRIMARY KEY (curriculum_day_id, slo_id)
);

CREATE TABLE client_curriculums (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id uuid NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    curriculum_id uuid NOT NULL REFERENCES curriculums(id),
    is_default boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(client_id, curriculum_id)
);

-- Seed grades
INSERT INTO grades (label, short_code, order_index) VALUES
    ('Grade 1', 'G1', 1),
    ('Grade 2', 'G2', 2),
    ('Grade 3', 'G3', 3),
    ('Grade 4', 'G4', 4),
    ('Grade 5', 'G5', 5);

-- Seed subjects
INSERT INTO subjects (label, short_code) VALUES
    ('English', 'Eng'),
    ('Maths', 'Maths'),
    ('Urdu', 'Urdu'),
    ('Science', 'Science');

-- Seed curriculum
INSERT INTO curriculums (name, board, academic_year, is_active) VALUES
    ('Punjab SNC 2020', 'Punjab', '2025-2026', true);

-- Seed curriculum_grade_subjects: Punjab x Grades 1-5 x English/Maths/Urdu
INSERT INTO curriculum_grade_subjects (curriculum_id, grade_id, subject_id)
SELECT c.id, g.id, s.id
FROM curriculums c
CROSS JOIN grades g
CROSS JOIN subjects s
WHERE c.board = 'Punjab'
  AND c.name = 'Punjab SNC 2020'
  AND s.short_code IN ('Eng', 'Maths', 'Urdu');
