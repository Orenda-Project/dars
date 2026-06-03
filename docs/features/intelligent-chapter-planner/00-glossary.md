# Glossary — Intelligent Chapter Planner

Terms used in the later docs. Future docs may only use terms defined here; add new ones as they emerge.

| Term | Definition |
|------|------------|
| **Chapter Planner** | The new LLM-driven service that takes (chapter, SLOs, sub-SLOs, period count) and produces a `ChapterPlan`. Replaces the deterministic `allocate_chapter_days` + `plan_chapter_slots` + `pick_lp_type` core as the primary path. |
| **ChapterPlan** | The planner's structured output: an ordered list of `PlanItem`s whose count equals the period count. The single artifact the LLM produces and the persistence layer consumes. |
| **PlanItem** | One element of a `ChapterPlan`. Either an **LP unit** or an **FA item**. Each PlanItem occupies exactly one teaching period (D-74 invariant: 1 item = 1 period). |
| **LP unit** | A PlanItem that is one lesson plan. Carries: ordered `topic_ids` it draws from (≥1, may merge or be a fraction of one — D-2), an `lp_type`, and the `sub_slo_ids` it teaches. Becomes one input to the LP Assistant. |
| **FA item** | A PlanItem that is one Formative Assessment. Carries the `sub_slo_ids` and `topic_ids` it assesses. Becomes one `class_assessment_slots` row (`assessment_type='formative'`). |
| **Period** | One teaching day on the CST's timetable (Mon–Fri minus holidays). The period count = real teaching days in the chapter's syllabus date range (existing `chapter_slot_count`, D-9). |
| **Topic** | A within-chapter teaching unit from the book (`topics` table). Has `topic_text` (OCR), `title`, and maps to sub-SLOs via `topic_sub_slos`. The planner draws LP `page_content` from topic text. |
| **SLO** | Curriculum-level Student Learning Outcome (`slos` table). A chapter teaches a set of SLOs via `book_chapter_slos`. |
| **sub-SLO** | Fine-grained learning skill under an SLO (`sub_slos` table). Mapped to topics via `topic_sub_slos`. The unit the planner attaches to LP units (taught) and FA items (assessed). |
| **lp_type** | Subject-specific lesson-plan type the LP Assistant understands (e.g. reading, vocabulary, grammar for Eng/Urdu; concrete, pictorial for Maths). Enum in `dars.v2_api.lp_types`. The planner picks one per LP unit; must pass `is_valid_lp_type`. |
| **Deterministic fallback** | The existing pure planners (`allocate_chapter_days`, `plan_chapter_slots`, `pick_lp_type`). Invoked when the LLM is unavailable, errors, or returns output that fails validation (D-3). Produces a valid `ChapterPlan` from the same inputs. |
| **PlanValidator** | Pure function that checks an LLM `ChapterPlan` against hard invariants (item count == periods, every topic covered by ≥1 LP unit, every LP `lp_type` valid for subject, FA sub-SLOs ⊆ chapter sub-SLOs, no empty LP units). Pass → use it; fail → fallback. |
| **class_lesson_slot_topics** | New join table (D-4): maps one `class_lesson_slots` row to N ordered topics, mirroring `class_assessment_slot_topics`. Lets an LP unit span multiple topics. |
| **PlannerLLM** | The interface the planner calls Claude through (D-10): `async complete(system, user) -> str`. Two backends — **ApiKeyPlannerLLM** (wraps `breakdown/llm_client.call_llm`; `ANTHROPIC_API_KEY`; **production**) and **AgentSdkPlannerLLM** (wraps `claude-agent-sdk` against a dev's Claude Code OAuth session; **development only**). Selected via `settings` (e.g. `PLANNER_LLM_BACKEND`). `claude-agent-sdk` is a dev/optional dependency, lazily imported. |
| **page_content** | Raw text fed to the LP Assistant/UG_EG as the lesson/exam source. For a multi-topic LP unit, the planner concatenates the constituent topics' `topic_text` in order. |
| **CST** | `class_subject_teachers` row — a teacher teaching one subject to one class. The plan is persisted as class slots scoped to a CST. |
