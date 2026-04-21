-- Master curriculum simplify: drop ownership columns from lesson_plans,
-- curriculums, and curriculum_topics.
-- Assumes no data exists.

ALTER TABLE lesson_plans DROP COLUMN IF EXISTS client_id;
ALTER TABLE lesson_plans DROP COLUMN IF EXISTS teacher_id;

ALTER TABLE curriculums DROP COLUMN IF EXISTS teacher_id;
ALTER TABLE curriculums DROP COLUMN IF EXISTS client_id;
ALTER TABLE curriculums DROP COLUMN IF EXISTS is_default;

ALTER TABLE curriculum_topics DROP COLUMN IF EXISTS completed_date;

ALTER TABLE lesson_plan_edits DROP COLUMN IF EXISTS client_id;
