-- Step 3: Academic Calendar cleanup
-- Add check constraint to academic_years to enforce end_date > start_date

ALTER TABLE academic_years
  ADD CONSTRAINT IF NOT EXISTS academic_years_dates_check CHECK (end_date > start_date);
