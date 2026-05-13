-- FK refactor: replace loose TEXT/INTEGER curriculum/grade/subject fields with
-- proper BIGINT FK columns referencing curriculums(id), grades(id), subjects(id).
-- DB is empty (no tenant data), so DROP + ADD is safe.

-- ============================================================
-- slos
-- ============================================================
ALTER TABLE slos DROP COLUMN IF EXISTS curriculum;
ALTER TABLE slos ADD COLUMN curriculum_id BIGINT NOT NULL REFERENCES curriculums(id);
ALTER TABLE slos DROP COLUMN IF EXISTS grade;
ALTER TABLE slos ADD COLUMN grade_id BIGINT NOT NULL REFERENCES grades(id);
ALTER TABLE slos DROP COLUMN IF EXISTS subject;
ALTER TABLE slos ADD COLUMN subject_id BIGINT NOT NULL REFERENCES subjects(id);

DROP INDEX IF EXISTS idx_slos_curriculum_grade_subject;
CREATE INDEX idx_slos_curriculum_grade_subject ON slos(curriculum_id, grade_id, subject_id);

-- ============================================================
-- books
-- ============================================================
ALTER TABLE books DROP COLUMN IF EXISTS curriculum;
ALTER TABLE books ADD COLUMN curriculum_id BIGINT NOT NULL REFERENCES curriculums(id);
ALTER TABLE books DROP COLUMN IF EXISTS grade;
ALTER TABLE books ADD COLUMN grade_id BIGINT NOT NULL REFERENCES grades(id);
ALTER TABLE books DROP COLUMN IF EXISTS subject;
ALTER TABLE books ADD COLUMN subject_id BIGINT NOT NULL REFERENCES subjects(id);

-- ============================================================
-- curriculum_chapter_schedule
-- ============================================================
ALTER TABLE curriculum_chapter_schedule DROP CONSTRAINT IF EXISTS uq_ccs_curriculum_chapter;
ALTER TABLE curriculum_chapter_schedule DROP COLUMN IF EXISTS curriculum;
ALTER TABLE curriculum_chapter_schedule ADD COLUMN curriculum_id BIGINT NOT NULL REFERENCES curriculums(id);
ALTER TABLE curriculum_chapter_schedule ADD CONSTRAINT uq_ccs_curriculum_chapter UNIQUE (curriculum_id, chapter_id);

-- ============================================================
-- class_subject_teachers
-- ============================================================
ALTER TABLE class_subject_teachers DROP CONSTRAINT IF EXISTS uq_cst_class_subject;
ALTER TABLE class_subject_teachers DROP COLUMN IF EXISTS subject;
ALTER TABLE class_subject_teachers ADD COLUMN subject_id BIGINT NOT NULL REFERENCES subjects(id);
ALTER TABLE class_subject_teachers ADD CONSTRAINT uq_cst_class_subject UNIQUE (class_id, subject_id);

-- ============================================================
-- school_classes
-- ============================================================
ALTER TABLE school_classes DROP COLUMN IF EXISTS grade;
ALTER TABLE school_classes ADD COLUMN grade_id BIGINT NOT NULL REFERENCES grades(id);

-- ============================================================
-- generated_lesson_plans
-- ============================================================
ALTER TABLE generated_lesson_plans DROP COLUMN IF EXISTS curriculum;
ALTER TABLE generated_lesson_plans ADD COLUMN curriculum_id BIGINT NOT NULL REFERENCES curriculums(id);
ALTER TABLE generated_lesson_plans DROP COLUMN IF EXISTS grade;
ALTER TABLE generated_lesson_plans ADD COLUMN grade_id BIGINT NOT NULL REFERENCES grades(id);
ALTER TABLE generated_lesson_plans DROP COLUMN IF EXISTS subject;
ALTER TABLE generated_lesson_plans ADD COLUMN subject_id BIGINT NOT NULL REFERENCES subjects(id);

-- ============================================================
-- generated_exams
-- ============================================================
ALTER TABLE generated_exams DROP COLUMN IF EXISTS curriculum;
ALTER TABLE generated_exams ADD COLUMN curriculum_id BIGINT NOT NULL REFERENCES curriculums(id);
ALTER TABLE generated_exams DROP COLUMN IF EXISTS grade;
ALTER TABLE generated_exams ADD COLUMN grade_id BIGINT NOT NULL REFERENCES grades(id);
ALTER TABLE generated_exams DROP COLUMN IF EXISTS subject;
ALTER TABLE generated_exams ADD COLUMN subject_id BIGINT NOT NULL REFERENCES subjects(id);

-- ============================================================
-- clients (nullable)
-- ============================================================
ALTER TABLE clients DROP COLUMN IF EXISTS curriculum;
ALTER TABLE clients ADD COLUMN curriculum_id BIGINT REFERENCES curriculums(id);
