-- Feature: teacher-adjustable-syllabus (D-2).
-- The class's own teaching path: which chapters the teacher chose to teach, in what
-- order, with dates. The global Syllabus Breakdown is now advisory; this is the
-- per-class source of truth for chapter sequencing. Picking a chapter inserts a row;
-- breaking it down (the existing /plan flow) is separate.
--
-- See docs/features/teacher-adjustable-syllabus/02-data-model.md.

CREATE TABLE class_chapters (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    cst_id          UUID NOT NULL REFERENCES class_subject_teachers(id) ON DELETE CASCADE,
    book_chapter_id UUID NOT NULL REFERENCES book_chapters(id),
    position        INT  NOT NULL,            -- teaching order within the class path
    start_date      DATE,                     -- teacher-set (D-7); break-it-down needs it
    end_date        DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cst_id, book_chapter_id),         -- a chapter appears once in a class path
    UNIQUE (cst_id, position)                 -- teaching order is unambiguous
);
CREATE INDEX idx_class_chapters_cst ON class_chapters(cst_id);
