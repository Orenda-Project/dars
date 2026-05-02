ALTER TABLE lesson_slots ALTER COLUMN scheduled_date TYPE TEXT USING scheduled_date::TEXT;
