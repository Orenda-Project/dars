ALTER TABLE assessments DROP COLUMN topic_id;
ALTER TABLE assessments ADD COLUMN lesson_plan_id UUID NOT NULL REFERENCES lesson_plans(id) ON DELETE CASCADE;
