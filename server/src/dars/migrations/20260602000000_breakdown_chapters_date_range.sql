-- Phase 1 (chapter-breakdown-and-plan): explicit per-chapter date ranges.
-- D-2: chapter timing becomes an explicit calendar range; teaching_days is
-- retained but becomes derived/display (see derived_teaching_days in reads).
-- Both nullable so existing rows + un-dated chapters stay valid.
-- See docs/features/chapter-breakdown-and-plan/02-data-model.md (Delta 1).

ALTER TABLE breakdown_chapters
    ADD COLUMN IF NOT EXISTS start_date DATE,
    ADD COLUMN IF NOT EXISTS end_date   DATE;
