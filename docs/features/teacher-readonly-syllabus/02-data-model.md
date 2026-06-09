# Data Model — Teacher Read-Only Syllabus

**No new schema. No migration (D-6).** Both tables already exist with every needed column. This doc records the auto-seed copy rule (D-2).

## Source: `syllabus_chapters` (org breakdown — existing)
From `20260604000000_syllabus_rename_drop_slots.sql`. Per chapter of a published `syllabus_breakdowns`:

| Column | Role |
|---|---|
| `syllabus_breakdown_id` | FK → the breakdown |
| `book_chapter_id` | which chapter |
| `position` | order, `1..N`; `UNIQUE (syllabus_breakdown_id, position)` |
| `start_date`, `end_date` | the org-decided date range — **non-null on every chapter of a published breakdown** (publish validation refuses undated chapters) |

## Target: `class_chapters` (teacher path — existing)
From `20260603100000_class_chapters.sql`:

| Column | Role |
|---|---|
| `org_id`, `cst_id` | tenancy + owner |
| `book_chapter_id` | which chapter |
| `position` | teaching order; `UNIQUE (cst_id, position)` |
| `start_date`, `end_date` | the chapter's date range — now **copied from the org breakdown** (was teacher-set) |
| — | `UNIQUE (cst_id, book_chapter_id)` — a chapter appears once |

## Auto-seed copy rule (D-2)

`seed_class_chapters_from_breakdown(conn, cst_id)` — called by the syllabus GET, idempotent:

1. Resolve the CST's published breakdown via `resolve_cst_syllabus_context` (curriculum via org, grade via class, subject direct → newest `published` `syllabus_breakdowns`). If none → seed nothing (D-7 empty state).
2. Read all `syllabus_chapters` for that breakdown (`book_chapter_id, position, start_date, end_date`, ordered by `position`).
3. For each, `INSERT INTO class_chapters (org_id, cst_id, book_chapter_id, position, start_date, end_date)` **only if** that `book_chapter_id` is not already present for the CST. Use `ON CONFLICT (cst_id, book_chapter_id) DO NOTHING` (and be safe against the `(cst_id, position)` unique constraint — if a legacy row already occupies a position, see Note).
4. Resolve `org_id` from the CST.

**Idempotency / re-seed:** Running it again inserts nothing once the path matches the breakdown. It does NOT update existing rows — so if the org later edits breakdown dates/order, those changes do not retro-apply to already-seeded CSTs in this feature (call out as a known limitation; a future "re-sync on breakdown change" is out of scope). 

**Note on position collisions:** Because legacy teacher-built paths may have arbitrary positions, seeding into a CST that already has *some* rows could collide on `(cst_id, position)`. Phase 1 must decide the safe rule — simplest: only auto-seed when the CST has **zero** `class_chapters` rows (clean install); a CST with a pre-existing partial path is left untouched and logged (legacy paths are a staging-only concern and can be cleared by re-seed). Confirm against staging data; document the chosen rule in Phase 1 Notes.

## What break-it-down reads (unchanged)
`generate_chapter_plan` reads the chapter's `(start_date, end_date)` from `class_chapters` (now org-sourced) and computes `chapter_slot_count` from the CST timetable. No change to that path.
