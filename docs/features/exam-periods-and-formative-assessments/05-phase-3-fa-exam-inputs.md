# Phase 3 — FA slots produce Exam Generator inputs

**Goal:** an FA slot carries Exam Generator inputs and can generate its exam end-to-end, the way a lesson slot carries Lesson Plan inputs and generates its LP — on demand, cache-first, mirroring `get_or_generate_lp`. Independently shippable.

Decisions in play: D-10, D-11. Reuses the existing `generated_exams` service.

---

## F-3.1 — Default FA Config per subject

**Spec:** Add `DEFAULT_FA_CONFIG: dict[str, dict]` (subject code → Question Config) somewhere near the exam service (e.g. `generated_exams/`), defining a short formative quiz per subject (D-10). Shape must match what `build_question_config` / `ExamRequest` expect (question types, counts, `include_answer_key`, etc.). A subject without a specific entry falls back to a sane generic formative default. Keep counts modest (formative ≠ summative).

**Acceptance:**
- `DEFAULT_FA_CONFIG['Eng']` (and the generic fallback) produce a valid `ExamRequest.question_config`.
- Looking up an unknown subject returns the generic default, never raises.

**Dependencies:** none.

---

## F-3.2 — `get_or_generate_exam_for_assessment_slot` entry point

**Spec:** In `generated_exams/service.py`, add an entry point mirroring `get_or_generate_lp` (D-10, D-11):
1. Load the assessment slot's context (reuse / extend `load_assessment_slot_context`): cst_id, curriculum/grade/subject, covered `topic_ids` (from `class_assessment_slot_topics`), joined `page_content`, the topics' `sub_slo_statements`.
2. `question_config = DEFAULT_FA_CONFIG[subject]`; `generation_type = 'formative'`.
3. Build the cache key via the existing `build_cache_key_global(curriculum_id, hash_topic_ids(topic_ids), 'formative', hash_question_config(config))`.
4. Cache-first: if a non-ERROR `generated_exams` row exists, link `class_assessment_slots.generated_exam_id` and return it.
5. Else insert pending, dispatch to UG_EG via the existing exam dispatch path, link the slot. Structured logging throughout (rule 11).

**Acceptance:**
- Calling it on an FA slot with no prior exam inserts a pending `generated_exams` row, dispatches, and sets the slot's `generated_exam_id`.
- A second call on a slot whose (topics, config, formative) key already has a READY exam returns the cached exam without re-dispatching.
- An ERROR-status cache row is retried, not returned.

**Dependencies:** F-3.1, Phase 2 (FA slots must exist).

---

## F-3.3 — Endpoint to generate an FA slot's exam

**Spec:** Add `POST /api/v2/assessment-slots/{id}/exam` (or extend `router_class_actions.py`) calling F-3.2 (D-11). Returns the exam status/id, same response idiom as the on-demand LP endpoint (PR #133). Org/access checks as for the slot's CST. Webhook completion already handled by the existing exam webhook router — confirm it links back to the slot via `generated_exam_id`.

**Acceptance:**
- `POST` on a valid FA slot returns 200 with the (pending or cached) exam.
- `POST` on a lesson slot id or a missing id → 404/422.
- On UG_EG webhook completion, the slot's exam shows READY with content (existing webhook path).

**Dependencies:** F-3.2.

---

## F-3.4 — Teacher UI: generate / view FA exam

**Spec:** In the teacher app, give an FA slot a "Generate exam" affordance (mirroring the per-slot "Generate LP" button from the on-demand-lp feature) and a view of the generated exam when READY. Minimal: button → calls F-3.3 → shows status → renders the exam when ready. No per-slot config editor (D-10; that's a fast-follow).

**Acceptance:**
- Teacher clicks "Generate exam" on an FA slot, sees in-flight status, then the rendered formative exam.
- The same slot re-opened shows the cached exam without regenerating.

**Dependencies:** F-3.3.

---

## Phase 3 ship criteria

All F-3.x acceptance met; both services green; an FA slot drives the exam-generation path end-to-end (default config), cache-first, with the teacher able to generate and view the formative exam. Per-slot editable exam config is the documented fast-follow (D-10).

## Notes from execution

- **`generation_type` for FAs is `'class_assessment'`, NOT `'formative'`.** D-10 wrote `generation_type='formative'`, but `ExamRequest.generation_type` (ug_eg_client) only accepts `{'exam', 'class_assessment'}` and would raise at construction on `'formative'`. The FA maps to `'class_assessment'` — the valid UG_EG enum value, which also round-trips through the F5.14 retry path (`retry_generated_exam` re-reads `generation_type` from the row and re-sends it). Exposed as the module constant `generated_exams.service.GENERATION_TYPE_FA`. *(Needs a decision-log entry — see build summary.)*
- **`sub_slo_statements` are NOT sent to UG_EG.** The glossary lists them among "Exam Generator inputs", but `ExamRequest` has no such field (it's an LP-Assistant concept; UG_EG derives questions from `page_content` + `question_config`). The on-demand FA path does not load or pass sub-SLO statements. Per-question→sub-SLO mapping is done downstream by the exam tagging service (F3.8/F3.9), not at request time.
- **The slot's `generated_exam_id` is linked by the service, NOT the webhook.** `get_or_generate_exam` (reused) calls `_link_slot_to_exam` at insert/cache-hit. The exam webhook only fills the `generated_exams` row by its own id (the callback URL carries our row id). Confirmed end-to-end.
- **`DEFAULT_FA_CONFIG` lives in `generated_exams/service.py`** (per this spec's "near the exam service") with a generic fallback via `default_fa_config(subject)` — deep-copies so callers can't mutate the module config. A separate per-subject map already existed in `generated_lps/batch_service.py` for the retry path; left untouched.
- **Endpoint:** `POST /api/v1/class-assessment-slots/{slot_id}/generate-exam` (prefix `/api/v1`, matching the on-demand-LP route). 404 missing/lesson-slot/cross-org; 422 on ValueError; 401 unauth.
- **Today-tab caveat:** the `/today` endpoint's `AssessmentSlotEntry` doesn't surface `exam_status`, so the today card defaults the FA button to "Generate exam" (in-flight driven by the poll); the timeline tab and the ExamViewer read the real status. A small follow-up could add `exam_status` to the today endpoint for a fully-stateful today card.
- No migration — reuses existing `generated_exams` + `class_assessment_slots`.
