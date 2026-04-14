-- grades
CREATE TABLE grades (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    label varchar(50) NOT NULL,
    short_code varchar(10) NOT NULL UNIQUE,
    order_index int NOT NULL
);

-- subjects
CREATE TABLE subjects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    label varchar(100) NOT NULL,
    short_code varchar(20) NOT NULL UNIQUE
);

-- slo_providers: NCP (federal), SNC Punjab, etc.
CREATE TABLE slo_providers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug varchar(50) NOT NULL UNIQUE,
    name varchar(255) NOT NULL,
    issuing_body varchar(255) NOT NULL,
    description text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- slos: actual SLO entries linked to a provider
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
    source_id int,
    is_active boolean NOT NULL DEFAULT true,
    UNIQUE(provider_id, code, grade_id, subject_id)
);
CREATE INDEX ON slos(provider_id);
CREATE INDEX ON slos(grade_id, subject_id);
