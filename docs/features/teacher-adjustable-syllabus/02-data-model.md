# Data Model — Teacher-Adjustable Syllabus (suggestion-led)

Ground truth for the schema after this feature. Migrations are append-only, run
automatically on Railway deploy. Never run DDL manually (CLAUDE.md rule 7). Migration
SQL cites this doc; this doc cites the SQL.

Base: the shipped `syllabus_breakdowns` / `syllabus_chapters` (global) +
`class_lesson_slots` / `class_assessment_slots` (per-CST, with `book_chapter_id`).

---

## What does NOT change

- `syllabus_breakdowns` / `syllabus_chapters` — unchanged. The global stays global and
  advisory (D-1). No `scope`/`cst_id` added (that was an abandoned approach).
- `class_lesson_slots` / `class_assessment_slots` — unchanged shape. Break-it-down still
  writes here. (Assessments simply stop being *generated* per D-8/D-9.)

## NEW — `class_chapters` (the class teaching path, D-2)

Migration: `server/src/dars/migrations/20260603100000_class_chapters.sql`

```sql
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
    UNIQUE (cst_id, position)                 -- positions unique within a class
);
CREATE INDEX idx_class_chapters_cst ON class_chapters(cst_id);
```

- `org_id` denormalized for the tenancy filter (CLAUDE.md rule 3), like the other class tables.
- `(cst_id, book_chapter_id)` unique — you can't add the same chapter twice.
- `(cst_id, position)` unique — teaching order is unambiguous; reorder rewrites positions.
- Cascades on CST delete.

## Chapter status — derived, no column (D-4)

Per `class_chapters` row, status is computed from the CST's generated slots for that
`book_chapter_id`:

```
slots = class_lesson_slots ∪ class_assessment_slots WHERE cst_id=? AND book_chapter_id=?
terminal = status IN ('taught','completed','skipped')
  no slots OR no terminal      -> 'yet_to_start'
  some terminal, not all       -> 'in_progress'
  all terminal (and ≥1 slot)   -> 'done'
```

(With assessments dropped per D-8, in practice this reads `class_lesson_slots` only, but
the union keeps it correct if assessment slots exist from earlier data.)

## Resolution / suggestion (D-3) — code only

- A CST's **path** = its `class_chapters` ordered by `position`.
- **Recommended next** = the global default's next chapter (by global `position`) not yet
  in the class path; if the path is empty, the global's first chapter (e.g. Ch 1).

## Break-it-down (Action 2, D-5) — uses class-path dates

`generate_chapter_plan` already takes `(cst_id, book_chapter_id)`. Change: it reads the
date range from the **`class_chapters`** row (not `syllabus_chapters`) and, per D-8,
generates lesson slots only.

## Assessments dropped (D-8 / D-9)

- **Generation-only (default, D-9a):** the planner's output is filtered to lesson/revision
  slots before insert; no `class_assessment_slots` rows created. Tables/endpoints/UI stay.
- **Full teardown (D-9b):** additionally remove assessment slots from timeline/today/
  mark-complete + drop the tables/UI. *Decide before Phase 2.*

## Schema-touching code

| Layer | What |
|---|---|
| Migration | `20260603100000_class_chapters.sql` |
| Path service | new: list path, pick (insert), reorder, remove, recommended-next, derived status |
| Resolution | `get_cst_syllabus` (Phase-1-shipped) now reads the class path + status + recommendation |
| Break-it-down | `generate_chapter_plan` reads dates from `class_chapters`; lessons-only (D-8) |
| Frontend | teacher-app: suggestion prompt, pick, statuses, reorder, set dates, break-it-down |
