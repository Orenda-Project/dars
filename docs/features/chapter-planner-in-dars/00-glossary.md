# Glossary

| Term | Definition |
|---|---|
| **CPE** | Chapter Planning Engine — the LLM planner that turns a chapter into an ordered sequence of lesson Plan Units. Originally the standalone `chapter-planner-app/`; this feature absorbs it into dars. |
| **Plan Unit** | One lesson plan. Carries `sequence`, `lp_type`, `topic_ids` (≥1), `slo_ids` (≥1), `topic_text` (member topics joined in id order), and a one-sentence `rationale`. Maps losslessly onto UG_LP's `/generate-lp` input. |
| **ChapterPlan** | The planner's output: `{subject, grade, curriculum, period_count, units: [PlanUnit]}`. Exactly `period_count` units. |
| **PlanRequest** | The planner's input: `{subject, grade, curriculum, period_count, chapter: {title, topics: [{id, topic_text, slos: [{id, statement}]}]}}`. |
| **lp_type** | The lesson-plan template kind (e.g. `reading`, `grammar`, `concrete`, `word_problems`, `revision`). Subject-constrained by `VALID_LP_TYPES`. |
| **VALID_LP_TYPES** | The per-subject allowed `lp_type` map. Lives in `UG_LessonPlan/config.py`; copied into the planner. The LLM may only pick from the list for the request's subject. |
| **D-8 invariants** | The five validation rules the planner output must satisfy: (a) exactly `period_count` units; (b) every chapter SLO covered by ≥1 unit; (c) each unit's `lp_type` allowed for the subject; (d) each unit has ≥1 real topic_id and ≥1 real slo_id; (e) `sequence` is a permutation of `1..period_count`. Named after D-8 in the standalone app's decision log; carried forward verbatim. |
| **agent-sdk backend** | The LLM client using `claude-agent-sdk` over the dev Claude Code OAuth session. The standalone app's planner backend; ported into dars (D-2). Mirrors how `book_import_service` already uses the SDK in the server. |
| **placeholder planner** | The current deterministic `generate_chapter_plan` body: one `class_lesson_slot` per topic + a final formative `class_assessment_slot`. Replaced by the CPE planner in Phase 2. |
| **break it down** | The teacher-app flow (F3.3) that calls `generate_chapter_plan` to materialise a chapter's slots for a CST. Entry point: `router_class_actions`. |
| **class_lesson_slots** | The per-CST lesson slot table the planner writes into. 1 slot = 1 teaching day (D-74 elsewhere). |
