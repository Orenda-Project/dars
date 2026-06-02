# Data Model — Syllabus Breakdown & Teacher Chapter Plan

Ground truth for the schema after this re-architecture. Migrations are append-only
and run automatically on Railway deploy. Never run DDL manually (CLAUDE.md rule 7).
Migration SQL cites this doc; this doc cites the SQL.

Base schema: v2 rebuild `docs/plans/2026-05-15-dars-v2-rebuild/02-data-model.md`.

---

## KEPT — data bank (untouched, D-11)

`curriculums, grades, subjects, slos, sub_slos, books, book_chapters, topics,
book_chapter_slos, topic_sub_slos`. No changes.

## KEPT — timetable / calendar (untouched, D-8)

`timetables, academic_years, org_holidays, school_holiday_overrides,
cst_holiday_overrides`. No changes. `projector.py`, `holidays.py`,
`chapter_calendar.derived_teaching_days` reused.

## KEPT — tenancy (untouched)

`organizations, org_admins, admin_sessions, schools, teachers, school_classes,
class_subject_teachers, cst_state`. No changes.

## RENAMED + REPURPOSED — Syllabus Breakdown (D-2, D-7)

Tables are **dropped and recreated** with syllabus naming (D-7). No data migration —
operational data was wiped 2026-06-02 and slots are dropped. The 2 global breakdowns
currently in `breakdowns` are dropped and **re-seeded** into the new tables (Phase 2).

### `syllabus_breakdowns` (was `breakdowns`, global-only)
```sql
CREATE TABLE syllabus_breakdowns (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id UUID NOT NULL REFERENCES curriculums(id),
    grade_id      UUID NOT NULL REFERENCES grades(id),
    subject_id    UUID NOT NULL REFERENCES subjects(id),
    book_id       UUID NOT NULL REFERENCES books(id),
    status        TEXT NOT NULL DEFAULT 'draft',   -- draft | published | deleted
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_syllabus_breakdowns_lookup
    ON syllabus_breakdowns(curriculum_id, grade_id, subject_id, status);
```
No `scope`/`scope_ref_id`/`parent_breakdown_id`/`previous_version_id` — global-only (D-3),
no forks. No `total_teaching_days` (derived).

### `syllabus_chapters` (was `breakdown_chapters`)
```sql
CREATE TABLE syllabus_chapters (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    syllabus_breakdown_id UUID NOT NULL REFERENCES syllabus_breakdowns(id) ON DELETE CASCADE,
    book_chapter_id       UUID NOT NULL REFERENCES book_chapters(id),
    position              INT  NOT NULL,
    start_date            DATE,
    end_date              DATE,
    UNIQUE (syllabus_breakdown_id, position)
);
```
No `teaching_days` (D-2 — derived). `start_date`/`end_date` are the artifact.

## DROPPED — old breakdown tables + admin slots (D-2, D-5, D-7)

Migration: `server/src/dars/migrations/20260604000000_syllabus_rename_drop_slots.sql`

```sql
-- order: children/FKs first
DROP TABLE IF EXISTS breakdown_slot_topics;
DROP TABLE IF EXISTS breakdown_slots;
DROP TABLE IF EXISTS breakdown_chapters;
DROP TABLE IF EXISTS breakdowns;

-- new syllabus tables (see CREATE statements above)
CREATE TABLE syllabus_breakdowns ( ... );
CREATE TABLE syllabus_chapters ( ... );

-- class slots lose their old source column (D-6)
ALTER TABLE class_lesson_slots     DROP COLUMN IF EXISTS breakdown_slot_id;
ALTER TABLE class_assessment_slots DROP COLUMN IF EXISTS breakdown_slot_id;

-- teacher Chapter Plan page ranges (D-15)
ALTER TABLE class_lesson_slots     ADD COLUMN page_start INT, ADD COLUMN page_end INT;
ALTER TABLE class_assessment_slots ADD COLUMN page_start INT, ADD COLUMN page_end INT;
```

## REPURPOSED — class slots (D-6, D-15)

### `class_lesson_slots`, `class_assessment_slots`, `class_assessment_slot_topics`
Kept. Now written by the teacher's break-it-down action (Phase 3), not realization.
- Drop `breakdown_slot_id` (above).
- **Page range kept (D-15):** `page_start`/`page_end` added to both slot tables (above) —
  on the class slots, NOT on any breakdown table.

## Schema-touching code to update in lockstep

| Layer | What |
|---|---|
| Migration | `20260604000000_syllabus_rename_drop_slots.sql` (drop old tables, create syllabus_*, drop breakdown_slot_id, add class-slot page ranges) |
| Re-seed | re-create the 2 global Syllabus Breakdowns into `syllabus_breakdowns`/`syllabus_chapters` (Phase 2 F2.5) |
| Schemas | rename `schemas_breakdown.py` → `schemas_syllabus.py`; `Syllabus*` read/write; drop all `BreakdownSlot*`/`AutoBuild*`/`Fork*`/`SeedChapter*` |
| Router | rename `router_breakdown.py` → `router_syllabus.py`; endpoints `/syllabus-breakdowns/...`; delete slot/seed/auto-build/fork endpoints |
| Deleted services | `fork_service.py`, `realize_service.py`, most of `auto_build_service.py` (salvage planners → `chapter_plan_service.py`, D-12) |
| Frontend | rename dashboard route `breakdowns` → `syllabus-breakdowns`; drop slot editor (date-range editor only); `dars-api.ts` `breakdowns` → `syllabusBreakdowns`; teacher-app gains break-it-down |

Verify exact references at implementation time via `graphify query`.
