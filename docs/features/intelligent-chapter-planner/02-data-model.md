# Data Model — Intelligent Chapter Planner

Ground truth for the schema. Migration SQL cites this doc; this doc cites the SQL. Only one additive change is needed (D-4); everything else reuses the existing v2 schema.

## Existing tables the planner reads (unchanged)

- **`topics`** — `id`, `book_chapter_id`, `topic_number`, `title`, `topic_text`. Source of LP `page_content`. Ordered by `topic_number`.
- **`book_chapter_slos`** — `(book_chapter_id, slo_id)`. The chapter's SLOs.
- **`topic_sub_slos`** — `(topic_id, sub_slo_id)`. Sub-SLOs per topic.
- **`slos`** / **`sub_slos`** — `code`, `statement`, `recommended_lp_type`, `position`. Statements feed the LLM and become LP `sub_slo_statements`.

## Existing tables the planner writes (unchanged columns)

- **`class_lesson_slots`** — `id`, `org_id`, `cst_id`, `position`, `slot_type` (`'lesson'|'revision'`), `lp_type`, `topic_id` (= **primary topic**, D-4), `book_chapter_id`, `status='planned'`. One row per LP unit / revision item.
- **`class_assessment_slots`** — `id`, `org_id`, `cst_id`, `position`, `assessment_type` (`'formative'` only this round, D-6), `book_chapter_id`, `status='scheduled'`. One row per FA item.
- **`class_assessment_slot_topics`** — `(class_assessment_slot_id, topic_id, position)`. FA coverage. Already exists; the planner writes the LLM-chosen `topic_ids` here.

## NEW table (D-4) — migration required

```sql
-- migrations/<ts>_class_lesson_slot_topics.sql
-- Maps one class lesson slot (LP unit) to N ordered topics, so an LP unit
-- can merge multiple book topics (intelligent-chapter-planner D-2/D-4).
-- Mirrors class_assessment_slot_topics.
CREATE TABLE IF NOT EXISTS class_lesson_slot_topics (
    class_lesson_slot_id UUID NOT NULL
        REFERENCES class_lesson_slots(id) ON DELETE CASCADE,
    topic_id             UUID NOT NULL
        REFERENCES topics(id),
    position             INT  NOT NULL,   -- order within the LP unit (1..N)
    PRIMARY KEY (class_lesson_slot_id, topic_id)
);

CREATE INDEX IF NOT EXISTS idx_class_lesson_slot_topics_slot
    ON class_lesson_slot_topics(class_lesson_slot_id);
```

Migration file goes in `server/src/dars/migrations/` only (project rule 7). Append-only; never edit after merge. Runs automatically on Railway deploy — no manual DDL.

### Relationship to `class_lesson_slots.topic_id`

`class_lesson_slots.topic_id` stays populated with the **primary topic** (the first topic in the LP unit's ordered list) for back-compat with the existing LP dispatch/cache (`generated_lps/service.py`), which keys on a single `topic_id`. The full ordered set lives in `class_lesson_slot_topics`. A single-topic LP unit therefore writes `topic_id` AND one join row pointing at the same topic.

## LP cache keying for multi-topic units (D-9)

No schema change. Multi-topic LP units route through the existing **class-scope** generation branch in `generated_lps/service.py` (built for teacher-added topic combos the global breakdown lacked — D-56/D-57 of the syllabus feature). Verify during Phase 2 that the class-scope key incorporates the full topic set; extend + log a follow-up decision if it only keys one topic.

## Invariant (carried from D-74)

1 PlanItem = 1 `position` = 1 teaching period. LP units and FA items share the single per-CST position sequence (`greatest(max(class_lesson_slots.position), max(class_assessment_slots.position))` + 1 per item), exactly as `generate_chapter_plan` does today.
