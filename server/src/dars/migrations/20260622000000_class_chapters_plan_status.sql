-- Feature: async-chapter-plan.
-- Break-it-down ("generate chapter plan") becomes an async background job with FE
-- polling. The job's lifecycle is tracked on the `class_chapters` row for the
-- (cst_id, book_chapter_id) being broken down:
--
--   PENDING    — dispatched, background task not yet running
--   GENERATING — background task is running the planner + persisting slots
--   READY      — plan generated, slots created
--   ERROR      — planner/transport failure; `error_message` holds the reason
--
-- Status values are UPPERCASE to match the generated_lps / generated_exams
-- status convention used elsewhere in the codebase.
--
-- Existing already-broken-down chapters default to 'READY' (they have slots and
-- no in-flight job), so the column is backfilled correctly for every prior row.
--
-- See docs/features (async-chapter-plan).

ALTER TABLE class_chapters
    ADD COLUMN status TEXT NOT NULL DEFAULT 'READY';

ALTER TABLE class_chapters
    ADD COLUMN error_message TEXT;

ALTER TABLE class_chapters
    ADD CONSTRAINT class_chapters_status_check
    CHECK (status IN ('PENDING', 'GENERATING', 'READY', 'ERROR'));

-- Lets the dispatch path cheaply find in-flight (PENDING/GENERATING) rows for a
-- CST without scanning, and supports per-cst status filtering.
CREATE INDEX idx_class_chapters_cst_status ON class_chapters(cst_id, status);
