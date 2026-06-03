# Phase 2 — Persist & Wire Behind `/plan`

**Goal:** Make the planner real end-to-end: build `PlanInputs` from DB, persist a `ChapterPlan` (incl. multi-topic LP units via the new join table), and swap it in behind the existing `/plan` endpoint with the deterministic path as fallback. Ships the migration.

Shippable to staging: a teacher hitting "break it down" gets an LLM-planned chapter; if the LLM is down, they get the deterministic plan — same endpoint, same response shape.

---

## F-2.1 — Migration: `class_lesson_slot_topics` (D-4)

**Spec.** Write `server/src/dars/migrations/<ts>_class_lesson_slot_topics.sql` exactly as in `02-data-model.md`. Additive only. No edits to `class_lesson_slots`.

**Acceptance.** Migration file present in the migrations dir; SQL is idempotent (`IF NOT EXISTS`). Applied automatically on deploy (no manual DDL — rule 7). A SQLite-compatible shape (the test suite runs on SQLite) — use `sqlalchemy.types.Uuid` conventions if a model is added; raw SQL table is fine since other join tables follow this pattern.

## F-2.2 — Build `PlanInputs` from DB

**Spec.** In `chapter_planner_service.py` (or a thin DB adapter beside it), `async build_plan_inputs(conn, *, book_chapter_id, subject_code, period_count) -> PlanInputs`: load topics (ordered by `topic_number`) with `title`/`topic_text`; load each topic's sub-SLOs (`topic_sub_slos` → `sub_slos`: id, code, statement, recommended_lp_type); load the chapter's SLOs (`book_chapter_slos` → `slos`). Filter by the curriculum/grade/subject already resolved by `resolve_cst_syllabus_context`. Structured logging on entry/exit with counts.

**Acceptance.** DB-gated integration test (mirrors existing `test_*` DB tests): against the seeded G1 English book, `build_plan_inputs` returns the chapter's topics each with ≥1 sub-SLO and a non-empty `topic_text`.

## F-2.3 — Persist a `ChapterPlan` (multi-topic aware)

**Spec.** `async persist_chapter_plan(conn, *, cst_id, org_id, book_chapter_id, plan: ChapterPlan)`:
- One transaction. Compute the start `position` as `generate_chapter_plan` does (max across both class slot tables).
- For each `PlanItem` in order, `position += 1`:
  - **LP unit** → insert `class_lesson_slots` with `slot_type='lesson'`, `lp_type`, `topic_id` = **primary topic** (first in `topic_ids`, D-4), `book_chapter_id`, `status='planned'`. Then insert one `class_lesson_slot_topics` row per topic (ordered `position` 1..N).
  - **FA item** → insert `class_assessment_slots` with `assessment_type='formative'`, `status='scheduled'`, `book_chapter_id`. Then `class_assessment_slot_topics` rows for its `topic_ids`.
- Return counts (lesson_slot_count, assessment_slot_count) for the endpoint response.

**Acceptance.** DB-gated test: persisting a 2-LP (one merging 2 topics) + 1-FA plan yields 2 lesson rows, 1 assessment row, the merged LP's `topic_id` == its first topic, and 2 `class_lesson_slot_topics` rows for it. Positions are contiguous and start after existing slots.

## F-2.4 — Swap into `generate_chapter_plan` (D-7, D-1)

**Spec.** Refactor `generate_chapter_plan` (in `chapter_plan_service.py`): keep all the front-matter (resolve context, chapter dates, `slot_count`, "already broken down" guard). Replace the allocate/pick/plan/persist block with: `inputs = build_plan_inputs(...)` → `plan = make_chapter_plan(inputs)` → `persist_chapter_plan(...)`. The `GeneratePlanResult` shape and the endpoint contract are unchanged (D-7). Add the plan `source` (`'llm'`/`'fallback'`) to `GeneratePlanResult.warnings` or a new field, and log it.

The `PlannerLLM` backend is resolved via `get_planner_llm(settings)` (D-10); production uses the API-key backend.

**Acceptance.** DB-gated end-to-end test: `POST /csts/{cst_id}/chapters/{id}/plan` against the seed with an injected fake `PlannerLLM` returning a valid plan → 200, class slots created, response counts match. A second test with the LLM raising → 200, slots still created via fallback. The existing "already broken down" and "no dates" 4xx behaviors still hold.

## F-2.5 — Sub-SLO statements flow to LP/FA dispatch (verify D-9)

**Spec.** Confirm the downstream dispatch (`generated_lps/service.py`, `router_generation.py`) picks up each LP unit's sub-SLOs as `LPRequest.sub_slo_statements` and that multi-topic LP units route through the class-scope cache branch (D-9). If the class-scope key only hashes a single `topic_id`, extend it to hash the ordered topic set and **log a follow-up decision (D-10) in `01-decision-log.md`**. `page_content` for a multi-topic LP unit = its topics' `topic_text` concatenated in order.

**Acceptance.** Test (DB-gated or unit on the dispatch builder): a multi-topic LP unit produces an `LPRequest` whose `page_content` concatenates both topics' text and whose `sub_slo_statements` lists the unit's sub-SLO statements; two distinct multi-topic units don't collide in the cache.

---

## Dependencies

- F-2.1 first (migration). F-2.2 → F-2.3 → F-2.4 sequential. F-2.5 after F-2.4.
- Depends on all of Phase 1.

## Notes from execution

_(append findings here during execution; don't alter specs above)_

- **F-2.5 doc typo:** the spec says "log a follow-up decision (D-10)" — D-10 already exists (PlannerLLM backends). Logged as **D-12** instead, per the parent task instruction and the decision-log's append-only rule.
- **F-2.5 needed the extension, not just verification:** the class-scope path (`get_or_generate_class_specific_lp`) keyed only on the single primary `topic_id`, loaded `page_content` from one topic, and unioned sub-SLOs from one topic. Extended to read `class_lesson_slot_topics`, build a topic-set cache key, concatenate topic_texts in order, and union sub-SLOs (D-12).
- **Pre-existing bug surfaced (out of scope, NOT fixed):** `generated_lps/service._parse_grade_int` expects a `'G<n>'` string, but `grades.code` is an `INT` column (seed values 1..12). The class-scope dispatch path passes `g.code` straight into `_parse_grade_int`, so it raises `TypeError`/`ValueError` on any real grade. The F-2.5 DB test stubs `_parse_grade_int` to exercise the D-12 assembly. Worth a separate bead.
- **Migration is Postgres-only:** `migrations.py` runs `.sql` via asyncpg; there is no SQLite path. The test suite's DB-gated tests therefore require a migrated Postgres (`DATABASE_URL`); the new table comes from the migration automatically. `class_assessment_slot_topics` is created the same way (in the cutover migration) — no special test-seed handling exists or is needed.
- **`generate_chapter_plan` keeps `fa_cadence`/`sa_per_chapter` params** for endpoint-signature compat but the new planner path ignores them (D-6: no summative; LLM decides FA cadence).
