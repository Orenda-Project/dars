# Phase 2 — Wire the planner into break-it-down; delete the standalone app

Replace the placeholder body of `generate_chapter_plan` with the ported CPE planner, persisting one `class_lesson_slot` per Plan Unit and **dropping** the auto-created assessment slot (D-1). Then delete `chapter-planner-app/` and the `make planner` target (D-3). Independently shippable: the teacher-app "break it down" flow now produces intelligent, SLO-covering lesson sequences.

Bead: `feat-chapter-planner-in-dars-phase-2-wire`.

Depends on: Phase 1 (planner core + models live in `breakdown/`).

## F2.1 — Build PlanRequest from the live connection (D-8)

**Spec:** In `chapter_plan_service.py`, add a helper that turns `(conn, book_chapter_id, subject, grade, period_count, curriculum)` into a `PlanRequest`, reusing the standalone `db.get_chapter_as_plan_input` query shape: topics ordered by `topic_number`; per-topic SLOs from `topic_sub_slos → sub_slos` ordered by `position, code`; sub_slo UUID as the SLO `id`; `"[code] statement"` as the statement; de-dup SLO ids within a topic. Use the request's `asyncpg.Connection` (the one `generate_chapter_plan` already holds) — do NOT open a second pool.
**Acceptance:** For a seeded G1 English chapter, the helper returns a PlanRequest that passes `PlanRequest` validation, with one topic per `topics` row and the chapter's sub-SLOs attached.

## F2.2 — Replace the placeholder in `generate_chapter_plan` (D-1, D-5)

**Spec:** `period_count` = the existing `slot_count` (teaching days from the CST timetable — unchanged; still gates generation, still refuses when 0 or chapter not in class path or already broken down). Build the PlanRequest (F2.1) for the chapter's subject/grade. Call `make_chapter_plan(req, AgentSdkPlannerLLM())`. Persist per unit, in `sequence` order, sharing the CST global position sequence (append after current max position), per the rule in **02-data-model.md** (D-9):
  - one `class_lesson_slot` — `slot_type='lesson'`, `lp_type=unit.lp_type`, `topic_id=unit.topic_ids[0]` (lead topic), `book_chapter_id`, `status='planned'`, tenancy cols; `RETURNING id`;
  - then one `class_lesson_slot_topics` row per `topic_id` in `unit.topic_ids` (order preserved), `position` 1..N — so a lesson plan tackling multiple topics records the full grouping.

  **Verify the live `class_lesson_slots` column set against the migrations** (`20260517` cutover has been ALTERed by `20260520`/`20260603100000`/`20260604`/`20260605` — `breakdown_slot_id` is gone, `book_chapter_id` is present) before writing the INSERT; the placeholder code in the current `chapter_plan_service.py` may itself be stale. **Delete** the `class_assessment_slots` INSERT block entirely (D-1). Update `GeneratePlanResult.source` to `"cpe"` (or similar); `assessment_slot_count` stays 0.
**Acceptance:** Break-it-down on a seeded chapter creates `slot_count`-worth of lesson slots (planner returns exactly `period_count=slot_count` units, so lesson_slot_count == slot_count), zero assessment slots, and for a unit that groups K topics there are K `class_lesson_slot_topics` rows with `position` 1..K and the slot's `topic_id` == the first of them. A planner failure (LLM/parse/validation) raises and is surfaced as a 4xx/5xx by `router_class_actions` (D-5) — no silent placeholder fallback. Existing `generate_chapter_plan` refusal cases (chapter not in path / already broken down / no teaching days) still raise as before.

## F2.3 — Reconcile pure slot-planner helpers

**Spec:** `allocate_chapter_days`, `plan_chapter_slots`, `compute_chapter_day_budget`, `PlannedSlot`, `ChapterDayAllocation` in `chapter_plan_service.py` were the old slot-sequence machinery. Check callers (grep showed only `chapter_plan_service` itself + tests). If nothing outside this module uses them after F2.2, remove the now-dead ones and their tests; keep any still referenced (e.g. `chapter_slot_count`, `resolve_cst_syllabus_context`, `compute_teaching_days` are still needed for `slot_count`). Do not remove `class_chapter_service`'s imports' targets.
**Acceptance:** No dead code left behind; `grep` confirms removed symbols have no remaining references; full test suite green.

## F2.4 — Update tests for the new behaviour

**Spec:** `server/tests/test_chapter_plan_service.py` and `test_slot_generation.py` currently assert the placeholder shape (lessons + a final FA). Update them: mock the planner LLM (inject a stub `PlannerLLM` — `generate_chapter_plan` should accept an optional injected backend for testability, defaulting to `AgentSdkPlannerLLM()`), assert lesson-only slots and zero assessment slots. Keep the multi-tenant / refusal-path tests.
**Acceptance:** `uv run pytest` green; no test still asserts an auto-created assessment slot from break-it-down.

## F2.5 — Delete the standalone app (D-3)

**Spec:** Remove `chapter-planner-app/` entirely. Remove the `planner` target and its `.PHONY` entry from the `Makefile`. Grep the repo for references to `chapter-planner-app` (docs, scripts, README) and clean them up. The standalone app's own feature folders (`docs/features/chapter-planner-engine/`, `docs/features/intelligent-chapter-planner/`) are historical record — leave them, but add a one-line "superseded by chapter-planner-in-dars (2026-06)" note at the top of each README.
**Acceptance:** `chapter-planner-app/` gone; `make planner` no longer exists; no live code or doc references the deleted directory (historical feature folders excepted, now annotated).

## Notes from execution

- **Persistence shape (F2.2).** Per Plan Unit in `sequence` order: one
  `class_lesson_slot` (`slot_type='lesson'`, `lp_type=unit.lp_type`,
  `topic_id=UUID(unit.topic_ids[0])` as the lead/primary topic, `book_chapter_id`,
  `status='planned'`, `org_id`/`cst_id` tenancy, `position` appended after the
  CST's current max across both slot tables) with `RETURNING id`, then one
  `class_lesson_slot_topics` row per `topic_id` in `unit.topic_ids` with
  `position` 1..N in list order. **No `class_assessment_slots` rows (D-1).**
  `GeneratePlanResult.source = "cpe"`; `assessment_slot_count` stays 0.
- **Lead-topic / multi-topic handling.** A unit's planner `topic_ids` are JSON
  strings (`build_plan_request` uses `t.id::text`, so ids are stringified UUIDs).
  On persist we `UUID(...)` them back. `slot.topic_id` == `UUID(unit.topic_ids[0])`;
  the join table carries the full ordered grouping (1..N). Verified by
  `test_generate_persists_lessons_only_with_topic_grouping` (K=2 unit).
- **Live `class_lesson_slots` columns reconciled** against migrations
  (`20260517` cutover + `20260604` drop of `breakdown_slot_id` + `20260605` add of
  `book_chapter_id`): the placeholder INSERT column list
  `(org_id, cst_id, position, slot_type, lp_type, topic_id, book_chapter_id, status)`
  was already correct, so it was reused (now with `RETURNING id`). No schema/migration.
- **F2.3 helpers removed** (all dead after F2.2; only referenced by this module +
  its old test): `compute_chapter_day_budget`, `allocate_chapter_days`,
  `plan_chapter_slots`, `ChapterDayAllocation`, `PlannedSlot`. The `pick_lp_type`
  import was dropped (planner now assigns lp_type). **Kept** (still used for
  slot_count gating / by `class_chapter_service` + `router_class_actions`):
  `chapter_slot_count`, `resolve_cst_syllabus_context`, `compute_teaching_days`,
  `CstSyllabusContext`, `_cst_weekday_set`.
- **Grade as int.** `PlanRequest.grade` needs an int 1..5; `resolve_cst_syllabus_context`
  only yields `grade_id`. `generate_chapter_plan` looks up `grades.code` (the int)
  for that id and passes it through. Curriculum is passed as `"ICT"` (the planner
  default — `PlanRequest.curriculum` is pass-through only, not load-bearing here).
- **No-fallback surfacing (F2.2, D-5).** `router_class_actions.break_down_chapter`
  now maps `PlannerLLMError` → 502 (mirrors `/api/v2/plan`) and keeps the existing
  `ValueError` → 422 (which also covers `PlanParseError`/`PlanValidationError`,
  both `ValueError` subclasses). `generate_chapter_plan` wraps its body in a
  try/except that logs at ERROR with `exc_info=True` and re-raises (rule 11).
- **Tests are DB-gated.** The persistence assertions need asyncpg-specific SQL
  (`RETURNING`, real FKs), so `test_chapter_plan_service.py` builds a throwaway
  org→…→chapter graph and is skipped without `DATABASE_URL` (same pattern as
  `test_chapter_breakdown_service.py`). Covers: lessons-only + zero assessment
  slots, a K=2 multi-topic unit, both refusal paths, planner-failure-persists-
  nothing, and the invalid-plan path. The old pure-helper tests were deleted with
  their helpers. Full suite: 229 passed / 41 skipped locally.
- **`make planner` divergence.** The phase doc expected a `planner` target in the
  root `dars/Makefile`; the Phase-1 branch base this stacks on has no such target
  (the Makefile only has `dev/test/db-new/bruno-sync/webapp/up/seed`). Nothing to
  remove — recorded here so the absence isn't read as a miss.
