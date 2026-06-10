# Phase 2 — Planner emits Formative Assessments

**Goal:** the Intelligent Chapter Planner decides where Formative Assessments belong in a chapter's slot sequence, and `generate_chapter_plan` persists those FA units as `class_assessment_slots`. No exam generation yet (Phase 3). Independently shippable.

Decisions in play: D-6, D-7, D-8, D-9, D-12, D-13. Contract change in `02-data-model.md`.

---

## F-2.1 — `PlanUnit` gains `slot_type`; `lp_type` becomes conditional

**Spec:** In `breakdown/planner_models.py`:
- Add `slot_type: str = Field(default='lesson')`, allowed values `'lesson' | 'formative_assessment'` (validator; reject others) (D-6, D-12, D-13).
- Make `lp_type: str | None`.
- Model validator: `slot_type='lesson'` ⇒ `lp_type` present and `∈ VALID_LP_TYPES[subject]`; `slot_type='formative_assessment'` ⇒ `lp_type` is None (D-7). (Subject isn't on `PlanUnit`, so the subject-membership check stays in `validate_plan` where the request is available; the unit-level validator only enforces the present/absent rule.)

**Acceptance:**
- A `PlanUnit` without `slot_type` parses as a lesson (back-compat, D-13).
- An FA unit with a non-null `lp_type` is rejected; a lesson unit without `lp_type` is rejected.
- Existing planner-model tests pass unchanged.

**Dependencies:** none.

---

## F-2.2 — `validate_plan` counts FAs toward coverage and the period total

**Spec:** In `breakdown/planner.py::validate_plan` (D-7, D-8):
- exactly `period_count` units total (lessons + FAs combined) — unchanged count, new composition.
- `lp_type ∈ VALID_LP_TYPES[subject]` checked only for lesson units.
- SLO-coverage: every chapter SLO appears in ≥1 unit's `slo_ids`, counting **both** lesson and FA units.
- `sequence` permutation of 1..period_count — unchanged.

**Acceptance:**
- A plan of N lessons (no FA) still validates (back-compat).
- A plan of (N−1) lessons + 1 FA where the FA covers the only otherwise-uncovered SLO validates.
- A plan where an FA carries an `lp_type` fails validation with a clear error.
- Wrong unit count, missing SLO coverage, bad permutation all still fail as before.

**Dependencies:** F-2.1.

---

## F-2.3 — Planner prompt instructs the LLM to place FAs

**Spec:** In `breakdown/planner_prompts.py`, extend the system prompt with a hard rule + a planning principle for Formative Assessments (D-6):
- Output each unit with a `slot_type` of `lesson` or `formative_assessment`.
- An FA unit has NO `lp_type`; it lists the `topic_ids` / `slo_ids` it assesses.
- Pedagogical guidance: place an FA after a cluster of related topics / before moving to a new strand, not every period; typically 0–2 per chapter depending on `period_count`; the FA's covered SLOs still count toward full chapter coverage.
- Total units must still equal `period_count` (an FA consumes a teaching day, D-8).
Update the user-prompt JSON contract / example to show the `slot_type` field. Keep the existing lesson rules intact.

**Acceptance:**
- The documented output schema in the prompt includes `slot_type`.
- A live (or recorded) planner run on a multi-topic chapter returns at least one `formative_assessment` unit with no `lp_type`, total units == `period_count`, full SLO coverage.
- A single-topic / tiny chapter may return zero FAs and still validate.

**Dependencies:** F-2.1, F-2.2.

---

## F-2.4 — `generate_chapter_plan` persists FA units as assessment slots

**Spec:** In `breakdown/chapter_plan_service.py::generate_chapter_plan`, change the persist loop (currently lines ~327–349, lesson-only) to branch on `unit.slot_type` (D-9):
- `'lesson'` → `class_lesson_slots` (+ `class_lesson_slot_topics`) exactly as today.
- `'formative_assessment'` → `class_assessment_slots` (`org_id`, `cst_id`, shared `position`, `assessment_type='formative'`, `book_chapter_id`, `status='scheduled'`) + one `class_assessment_slot_topics` row per covered topic (position 1..N). Bump `result.assessment_slot_count`.
Both kinds share the single incrementing `position` (the merged sequence already computed at lines ~313–323). Update the docstring (currently says "No assessment slots are created (D-1)" — that prior-feature D-1 is now superseded for this path by this feature's D-9; note the supersession inline).

**Acceptance:**
- Breaking down a chapter whose plan contains FA units creates the right number of `class_lesson_slots` and `class_assessment_slots`, positions contiguous and interleaved by `sequence`.
- `GenerateChapterPlanResponse` reports `assessment_slot_count > 0` when FAs were planned.
- The projector (`project_cst_schedule`) dates lesson + FA slots together with no gaps/overlaps (existing merge-by-position logic, unchanged).
- A chapter whose plan is all lessons behaves exactly as before.

**Dependencies:** F-2.1, F-2.2.

---

## F-2.5 — Teacher timeline/calendar shows FA slots

**Spec:** Confirm the teacher-app timeline (`GET /csts/{id}/timeline` + the Timeline tab) already renders `class_assessment_slots` (the class-timeline-view feature interleaves both tables). If FA slots render with a sensible label/badge, no UI work; if assessment slots were never exercised because none existed, add the minimal rendering (badge "Formative Assessment", covered-topic list). Mark-taught/complete affordance can stay as-is for this phase.

**Acceptance:**
- After break-it-down, an FA slot appears in the teacher timeline on its projected date, visually distinct from a lesson, never on an exam/holiday date (Phase 1 guarantee).

**Dependencies:** F-2.4.

---

## Phase 2 ship criteria

All F-2.x acceptance met; both services green; breaking a chapter down produces interleaved lesson + FA slots, dated correctly, with full SLO coverage and no FA on excluded dates. FA slots have no exam generation yet — that's Phase 3.
