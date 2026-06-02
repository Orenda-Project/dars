-- Phase 2 (syllabus-breakdown-and-teacher-chapter-plan): demolition + table rename.
-- D-2/D-3/D-5/D-7: drop the old breakdown tables + admin slots; create syllabus_*
-- tables (global-only, chapter->date-range); strip class slots of their old
-- breakdown source; add teacher Chapter Plan page ranges (D-15).
--
-- No data migration: operational data was wiped 2026-06-02 and slots are gone.
-- The 2 global Syllabus Breakdowns are re-seeded into the new tables separately
-- (Phase 2 F2.5 re-seed step, run against staging directly).
--
-- See docs/features/syllabus-breakdown-and-teacher-chapter-plan/02-data-model.md.

-- 1. Drop the class-slot FK columns that reference breakdown_slots FIRST,
--    otherwise the breakdown_slots drop fails (DependentObjectsStillExist).
ALTER TABLE class_lesson_slots     DROP COLUMN IF EXISTS breakdown_slot_id;
ALTER TABLE class_assessment_slots DROP COLUMN IF EXISTS breakdown_slot_id;

-- 2. Drop old breakdown tables (children/FK first).
DROP TABLE IF EXISTS breakdown_slot_topics;
DROP TABLE IF EXISTS breakdown_slots;
DROP TABLE IF EXISTS breakdown_chapters;
DROP TABLE IF EXISTS breakdowns;

-- 2. New syllabus tables (global-only, no forks, no slots).
CREATE TABLE syllabus_breakdowns (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id UUID NOT NULL REFERENCES curriculums(id),
    grade_id      UUID NOT NULL REFERENCES grades(id),
    subject_id    UUID NOT NULL REFERENCES subjects(id),
    book_id       UUID NOT NULL REFERENCES books(id),
    status        TEXT NOT NULL DEFAULT 'draft',   -- draft | published | deleted
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_syllabus_breakdowns_lookup
    ON syllabus_breakdowns(curriculum_id, grade_id, subject_id, status);

CREATE TABLE syllabus_chapters (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    syllabus_breakdown_id UUID NOT NULL REFERENCES syllabus_breakdowns(id) ON DELETE CASCADE,
    book_chapter_id       UUID NOT NULL REFERENCES book_chapters(id),
    position              INT  NOT NULL,
    start_date            DATE,
    end_date              DATE,
    UNIQUE (syllabus_breakdown_id, position)
);

-- 4. Teacher Chapter Plan page ranges on the class slots (D-15).
--    (breakdown_slot_id columns were dropped in step 1, above.)
ALTER TABLE class_lesson_slots     ADD COLUMN IF NOT EXISTS page_start INT,
                                   ADD COLUMN IF NOT EXISTS page_end   INT;
ALTER TABLE class_assessment_slots ADD COLUMN IF NOT EXISTS page_start INT,
                                   ADD COLUMN IF NOT EXISTS page_end   INT;
