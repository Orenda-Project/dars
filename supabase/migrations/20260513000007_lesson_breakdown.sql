-- Add indexes for faster slot lookup by chapter_plan_id
CREATE INDEX IF NOT EXISTS idx_class_lesson_slots_chapter_plan
  ON class_lesson_slots(chapter_plan_id);
CREATE INDEX IF NOT EXISTS idx_assessment_slots_chapter_plan
  ON assessment_slots(chapter_plan_id);
