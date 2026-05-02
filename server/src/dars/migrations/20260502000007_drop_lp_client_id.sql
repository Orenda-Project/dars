-- Lesson plans are global curriculum content; client ownership is not needed.
ALTER TABLE lesson_plans DROP COLUMN IF EXISTS client_id;
