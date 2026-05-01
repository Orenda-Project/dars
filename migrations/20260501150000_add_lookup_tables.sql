-- Lookup tables for canonical curriculum, subject, and grade values.
-- These let us enforce FK constraints so bad values are caught at the DB layer.

CREATE TABLE IF NOT EXISTS curriculums (
    code TEXT PRIMARY KEY  -- 'ICT', 'Punjab', 'Sindh'
);

CREATE TABLE IF NOT EXISTS subjects (
    code TEXT PRIMARY KEY  -- 'Eng', 'Maths', 'Urdu', 'Science', 'GK'
);

CREATE TABLE IF NOT EXISTS grades (
    grade INTEGER PRIMARY KEY  -- 1-5
);

-- Which subjects are valid for which curriculum
CREATE TABLE IF NOT EXISTS curriculum_subjects (
    curriculum_code TEXT NOT NULL REFERENCES curriculums(code) ON DELETE CASCADE,
    subject_code    TEXT NOT NULL REFERENCES subjects(code) ON DELETE CASCADE,
    PRIMARY KEY (curriculum_code, subject_code)
);

-- Seed data
INSERT INTO curriculums (code) VALUES ('ICT'), ('Punjab'), ('Sindh') ON CONFLICT DO NOTHING;

INSERT INTO subjects (code) VALUES ('Eng'), ('Maths'), ('Urdu'), ('Science'), ('GK') ON CONFLICT DO NOTHING;

INSERT INTO grades (grade) VALUES (1),(2),(3),(4),(5) ON CONFLICT DO NOTHING;

INSERT INTO curriculum_subjects (curriculum_code, subject_code) VALUES
    ('ICT',    'Eng'),
    ('ICT',    'Maths'),
    ('ICT',    'Urdu'),
    ('ICT',    'Science'),
    ('Punjab', 'Eng'),
    ('Punjab', 'Maths'),
    ('Punjab', 'Urdu'),
    ('Sindh',  'Eng'),
    ('Sindh',  'Maths'),
    ('Sindh',  'Urdu'),
    ('Sindh',  'Science'),
    ('Sindh',  'GK')
ON CONFLICT DO NOTHING;

-- Fix bad data in lesson_plans before adding FK
UPDATE lesson_plans SET subject = 'Eng' WHERE subject = 'English';

-- Add FK constraints on books
ALTER TABLE books
    ADD CONSTRAINT fk_books_curriculum FOREIGN KEY (curriculum) REFERENCES curriculums(code),
    ADD CONSTRAINT fk_books_subject    FOREIGN KEY (subject)    REFERENCES subjects(code),
    ADD CONSTRAINT fk_books_grade      FOREIGN KEY (grade)      REFERENCES grades(grade);

-- Add FK constraints on lesson_plans (grade is TEXT so we skip the grades FK here)
ALTER TABLE lesson_plans
    ADD CONSTRAINT fk_lp_curriculum FOREIGN KEY (curriculum) REFERENCES curriculums(code),
    ADD CONSTRAINT fk_lp_subject    FOREIGN KEY (subject)    REFERENCES subjects(code);

-- Add FK constraints on exam_generations
ALTER TABLE exam_generations
    ADD CONSTRAINT fk_eg_curriculum FOREIGN KEY (curriculum) REFERENCES curriculums(code),
    ADD CONSTRAINT fk_eg_subject    FOREIGN KEY (subject)    REFERENCES subjects(code),
    ADD CONSTRAINT fk_eg_grade      FOREIGN KEY (grade)      REFERENCES grades(grade);
