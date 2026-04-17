-- Migration: normalize curriculum schema
-- - slos: drop grade_id, subject_id; add book_id
-- - curriculums: drop grade_id, subject_id, academic_year; add is_default, teacher_id, client_id
-- - curriculum_topics: add planned_date, completed_date
-- - curriculum_lp_stubs: add planned_date
-- - topics: add text column
-- - books: rename curriculum -> board

-- ============================================================
-- 1. slos: replace grade_id + subject_id with book_id
-- ============================================================

-- Drop the old unique constraint that references grade_id + subject_id
ALTER TABLE slos DROP CONSTRAINT IF EXISTS slos_provider_id_code_grade_id_subject_id_key;
ALTER TABLE slos DROP CONSTRAINT IF EXISTS slos_unique;

-- Drop old indexes on grade_id/subject_id
DROP INDEX IF EXISTS slos_grade_id_subject_id_idx;

-- Add book_id (nullable first so existing rows don't fail)
ALTER TABLE slos ADD COLUMN book_id integer REFERENCES books(id);

-- Drop the old FK columns
ALTER TABLE slos DROP COLUMN grade_id;
ALTER TABLE slos DROP COLUMN subject_id;

-- Now make book_id NOT NULL (only safe if all rows have been updated;
-- for a fresh DB this is fine — production data migration handled separately)
ALTER TABLE slos ALTER COLUMN book_id SET NOT NULL;

-- New unique constraint: one code per provider+book
ALTER TABLE slos ADD CONSTRAINT slos_provider_id_book_id_code_key UNIQUE (provider_id, book_id, code);

CREATE INDEX ON slos(book_id);

-- ============================================================
-- 2. curriculums: remove grade_id, subject_id, academic_year;
--    add is_default, teacher_id, client_id
-- ============================================================

ALTER TABLE curriculums DROP COLUMN IF EXISTS grade_id;
ALTER TABLE curriculums DROP COLUMN IF EXISTS subject_id;
ALTER TABLE curriculums DROP COLUMN IF EXISTS academic_year;

ALTER TABLE curriculums ADD COLUMN is_default boolean NOT NULL DEFAULT false;
ALTER TABLE curriculums ADD COLUMN teacher_id uuid REFERENCES teachers(id) ON DELETE SET NULL;
ALTER TABLE curriculums ADD COLUMN client_id uuid REFERENCES clients(id) ON DELETE CASCADE;

CREATE INDEX ON curriculums(teacher_id);
CREATE INDEX ON curriculums(client_id);
CREATE INDEX ON curriculums(book_id);
CREATE INDEX ON curriculums(is_default);

-- ============================================================
-- 3. curriculum_topics: add planned_date, completed_date
-- ============================================================

ALTER TABLE curriculum_topics ADD COLUMN planned_date date;
ALTER TABLE curriculum_topics ADD COLUMN completed_date date;

-- ============================================================
-- 4. curriculum_lp_stubs: add planned_date
-- ============================================================

ALTER TABLE curriculum_lp_stubs ADD COLUMN planned_date date;

-- ============================================================
-- 5. topics: add text column
-- ============================================================

ALTER TABLE topics ADD COLUMN text text;

-- ============================================================
-- 6. books: rename column curriculum -> board
-- ============================================================

ALTER TABLE books RENAME COLUMN curriculum TO board;

DROP INDEX IF EXISTS idx_books_curriculum;
CREATE INDEX idx_books_board ON books(board);
