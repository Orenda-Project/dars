-- Phase 3 (syllabus-breakdown-and-teacher-chapter-plan): class slots gain a
-- direct chapter link (D-16). The old timeline grouped slots by chapter via the
-- dropped breakdown_slots->breakdown_chapters join; in the teacher-generated
-- model each class slot belongs to the book chapter it was generated from.
-- Nullable for safety; always set by the "break it down" generation.
--
-- See docs/features/syllabus-breakdown-and-teacher-chapter-plan/02-data-model.md.

ALTER TABLE class_lesson_slots
    ADD COLUMN IF NOT EXISTS book_chapter_id UUID REFERENCES book_chapters(id);
ALTER TABLE class_assessment_slots
    ADD COLUMN IF NOT EXISTS book_chapter_id UUID REFERENCES book_chapters(id);

CREATE INDEX IF NOT EXISTS idx_class_lesson_slots_chapter
    ON class_lesson_slots(book_chapter_id);
CREATE INDEX IF NOT EXISTS idx_class_assessment_slots_chapter
    ON class_assessment_slots(book_chapter_id);
