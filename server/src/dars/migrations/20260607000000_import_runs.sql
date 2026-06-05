-- migrations/20260607000000_import_runs.sql
-- Tracks one background "import a taleemabad-core book into Dars" run
-- (core-book-import D-1). Status + per-step progress + counts + error so the
-- admin dashboard can poll a long-running import. See
-- docs/features/core-book-import/02-data-model.md.
CREATE TABLE IF NOT EXISTS import_runs (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    core_book_id  INT          NOT NULL,                  -- fde_staging.book_library_book.id
    curriculum_id UUID         NOT NULL,                  -- resolved Dars cell
    grade_id      UUID         NOT NULL,
    subject_id    UUID         NOT NULL,
    dars_book_id  UUID,                                   -- set once the book upserts
    status        TEXT         NOT NULL DEFAULT 'pending',-- pending|running|succeeded|failed
    current_step  TEXT,                                   -- slos|sub_slos|book_chapters|topics|mappings
    steps         JSONB        NOT NULL DEFAULT '{}'::jsonb,  -- per-step {status,count}
    counts        JSONB        NOT NULL DEFAULT '{}'::jsonb,  -- final row counts
    warnings      JSONB        NOT NULL DEFAULT '[]'::jsonb,  -- non-fatal notes
    error         TEXT,                                   -- set when status='failed'
    started_by    TEXT,                                   -- admin identifier (require_admin)
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- One-running-at-a-time guard (D-8) reads by status.
CREATE INDEX IF NOT EXISTS ix_import_runs_status
    ON import_runs(status);

-- History list ordering.
CREATE INDEX IF NOT EXISTS ix_import_runs_created_at
    ON import_runs(created_at DESC);
