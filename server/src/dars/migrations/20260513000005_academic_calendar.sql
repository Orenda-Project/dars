-- Step 3: Academic Calendar cleanup
-- Add check constraint to academic_years to enforce end_date > start_date

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'academic_years_dates_check'
  ) THEN
    ALTER TABLE academic_years
      ADD CONSTRAINT academic_years_dates_check CHECK (end_date > start_date);
  END IF;
END
$$;
