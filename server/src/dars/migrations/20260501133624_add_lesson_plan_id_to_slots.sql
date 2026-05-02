ALTER TABLE lesson_slots ADD COLUMN IF NOT EXISTS lesson_plan_id UUID REFERENCES lesson_plans(id) ON DELETE SET NULL;
