-- Add day_number to assessment_slots and make scheduled_date nullable.
-- Breakdown algorithm now owns the full sequence; dates are derived from day_number.
ALTER TABLE assessment_slots ADD COLUMN IF NOT EXISTS day_number INTEGER;
ALTER TABLE assessment_slots ALTER COLUMN scheduled_date DROP NOT NULL;
