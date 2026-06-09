# Data Model — Chapter Planner in Dars

**No new schema. No migration.** This feature reuses tables that already exist on staging. This doc records the slot↔topic relationship the planner writes into (D-9) so Phase 2's persistence is unambiguous.

## The lesson-slot ↔ topic relationship (one slot, N topics)

A Plan Unit groups ≥1 `topic_ids` (D-9: a lesson plan may tackle multiple topics). Two existing tables hold this:

### `class_lesson_slots` (existing — `20260517000000` + later ALTERs)
One row per Plan Unit. Relevant columns as deployed today (after `20260604` drop of `breakdown_slot_id` and `20260605` add of `book_chapter_id`):

| Column | Use by the planner |
|---|---|
| `id` | PK |
| `org_id`, `cst_id` | tenancy + owner (existing) |
| `position` | the unit's place in the CST global slot sequence (append after current max; `UNIQUE (cst_id, position)`) |
| `slot_type` | `'lesson'` |
| `lp_type` | `unit.lp_type` |
| `topic_id` | **lead/primary topic** = `unit.topic_ids[0]` (back-compat; `ON DELETE SET NULL`) |
| `book_chapter_id` | the chapter being broken down |
| `status` | `'planned'` |

> `topic_id` is intentionally kept as a single lead topic for back-compat (the join table is the source of truth for the full grouping). Confirm the exact live column set against the migrations before writing the INSERT — do not trust the original cutover DDL alone (it has been ALTERed by `20260520`, `20260603100000`, `20260604`, `20260605`).

### `class_lesson_slot_topics` (existing — `20260606000000`)
The full grouping. One row per topic in the unit.

| Column | Use |
|---|---|
| `class_lesson_slot_id` | FK → the `class_lesson_slots` row (`ON DELETE CASCADE`) |
| `topic_id` | a member topic (FK → `topics`) |
| `position` | order within the unit, `1..N`, in `unit.topic_ids` order |
| PK | `(class_lesson_slot_id, topic_id)` |

`generated_lps/service.py` already READS this table (ordered by `position`) to assemble the LP's page content when a unit spans multiple topics — so populating it makes downstream generation pick up the full grouping for free.

## Persistence rule (Phase 2, F2.2)

For each `unit` in the ChapterPlan, in `sequence` order:
1. `INSERT class_lesson_slots` — `slot_type='lesson'`, `lp_type=unit.lp_type`, `topic_id=unit.topic_ids[0]`, `book_chapter_id`, `position=++pos`, `status='planned'`, tenancy cols. `RETURNING id`.
2. For each `topic_id` in `unit.topic_ids` (order = list order), `INSERT class_lesson_slot_topics (class_lesson_slot_id, topic_id, position)` with `position` = 1..N.

No `class_assessment_slots` rows are created (D-1).

## Tables this feature does NOT touch

`class_assessment_slots`, `class_assessment_slot_topics`, `breakdown_slots`, `syllabus_*`. Reads only: `topics`, `topic_sub_slos`, `sub_slos`, `book_chapters`, `class_chapters` (for `slot_count` gating — unchanged).
