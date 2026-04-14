-- Migration: sub_slos, topics, topic_sub_slos, curriculums, curriculum_topics, curriculum_lp_stubs

CREATE TABLE sub_slos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slo_id uuid NOT NULL REFERENCES slos(id),
    code varchar(50) NOT NULL,
    statement text NOT NULL DEFAULT '',
    source_id int,
    is_active boolean NOT NULL DEFAULT true,
    UNIQUE(slo_id, code)
);
CREATE INDEX ON sub_slos(slo_id);

CREATE TABLE topics (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id int NOT NULL REFERENCES book_chapters(id) ON DELETE CASCADE,
    title text NOT NULL,
    sequence int NOT NULL,
    source_id int,
    UNIQUE(chapter_id, sequence)
);
CREATE INDEX ON topics(chapter_id);

CREATE TABLE topic_sub_slos (
    topic_id uuid NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    sub_slo_id uuid NOT NULL REFERENCES sub_slos(id),
    PRIMARY KEY (topic_id, sub_slo_id)
);

CREATE TABLE curriculums (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(255) NOT NULL,
    grade_id uuid NOT NULL REFERENCES grades(id),
    subject_id uuid NOT NULL REFERENCES subjects(id),
    book_id int NOT NULL REFERENCES books(id),
    provider_id uuid NOT NULL REFERENCES slo_providers(id),
    academic_year varchar(20),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE curriculum_topics (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id uuid NOT NULL REFERENCES curriculums(id) ON DELETE CASCADE,
    topic_id uuid NOT NULL REFERENCES topics(id),
    sequence int NOT NULL,
    UNIQUE(curriculum_id, sequence)
);
CREATE INDEX ON curriculum_topics(curriculum_id);

CREATE TABLE curriculum_lp_stubs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_topic_id uuid NOT NULL REFERENCES curriculum_topics(id) ON DELETE CASCADE,
    skill_type varchar(50),
    cpa_phase varchar(50),
    blooms_level varchar(30),
    sequence int NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'pending',
    lesson_plan_id uuid REFERENCES lesson_plans(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(curriculum_topic_id, sequence)
);
CREATE INDEX ON curriculum_lp_stubs(curriculum_topic_id);
CREATE INDEX ON curriculum_lp_stubs(status);
