# Glossary

Every Term-Capitalised-Word used in the other docs is defined here. Future docs may only use terms defined here. If a new term emerges mid-execution, add it.

## Existing concepts (carried in from prior features — defined here for self-containment)

- **Syllabus Breakdown** — the admin/global reference calendar of chapter→date-range for a (curriculum, grade, subject) triple. Table `syllabus_breakdowns`, scope always `'global'`. Holds chapter date ranges only — no slots. (prior D-1, D-2)
- **Syllabus Chapter** — a chapter row inside a Syllabus Breakdown, table `syllabus_chapters`: `book_chapter_id`, `position`, `start_date`, `end_date`, derived `teaching_days`.
- **CST** — Class-Subject-Teacher: a teacher teaching one subject to one class. Row in `class_subject_teachers`. The unit a Chapter Plan is generated for.
- **Chapter Plan** — the teacher-app, class-specific slot sequence for one chapter, produced by "break it down". One per CST per chapter. Persists `class_lesson_slots` (+ `class_lesson_slot_topics`) today.
- **Class Chapter** — a chapter on the teacher's own teaching path, table `class_chapters` (`cst_id`, `book_chapter_id`, `position`, `start_date`, `end_date`). The teacher's dates here — NOT the global syllabus dates — gate the Chapter Plan's slot count (prior D-5).
- **Effective Holidays** — the resolved holiday date set for a CST: org holidays ± school overrides ± CST overrides (prior D-26). Function `get_effective_holidays(conn, cst_id)`.
- **Teaching Day** — a date inside a range that falls on a timetable weekday and is not a holiday. Computed by `compute_teaching_days(start, end, weekday_set, holidays)`.
- **Slot** — one teaching day's worth of plan. 1 slot = 1 teaching day (prior D-9/D-74). Two physical tables: `class_lesson_slots` and `class_assessment_slots`, merged by `position` for projection.
- **Lesson Slot** — a `class_lesson_slots` row: `slot_type='lesson'`, an `lp_type`, a lead `topic_id` + a `class_lesson_slot_topics` grouping. Drives Lesson Plan generation.
- **Assessment Slot** — a `class_assessment_slots` row: `assessment_type ∈ ('formative','summative')`, a `class_assessment_slot_topics` grouping, a `generated_exam_id`. Table exists; **not populated by the planner before this feature**.
- **Projector** — `project_cst_schedule` / `project_schedule` in `breakdown/projector.py`: assigns projected calendar dates to a CST's slots by walking the teaching-day list 1:1.
- **Intelligent Chapter Planner** — the LLM-driven planner (`breakdown/planner.py::make_chapter_plan`) that turns a `PlanRequest` into a `ChapterPlan` of `PlanUnit`s. Validated against hard invariants; no fallback (prior D-5/D-8).
- **PlanUnit** — one item in a `ChapterPlan`: `sequence`, `lp_type`, `topic_ids`, `slo_ids`, `topic_text`, `rationale`. **This feature adds `slot_type`.**
- **Lesson Plan inputs** — the fields a lesson slot carries that drive `get_or_generate_lp` → `LPRequest` to LP Assistant: curriculum/grade/subject, `page_content` (topic text), `lp_type`, `sub_slo_statements`.
- **Exam Generator inputs** — the analogous fields an assessment slot carries that drive the `generated_exams` service → `ExamRequest` to UG_EG: curriculum/grade/subject, `page_content` (joined topic text), `generation_type`, and a **Question Config**. *Note (D-19/D-20):* the real `ExamRequest` has no `sub_slo_statements` field (UG_EG derives questions from `page_content` + `question_config`), and its `generation_type` enum is `{'exam','class_assessment'}` — an FA maps to `'class_assessment'`, there is no `'formative'`.
- **Question Config** — the exam shape passed to UG_EG: question types, counts, answer-key flag, etc. Hashed into the exam cache key (`build_question_config`, `hash_question_config`).

## New concepts (introduced by this feature)

- **Exam Period** — a reserved date range on a Syllabus Breakdown during which no teaching happens. Table `exam_periods`: `syllabus_breakdown_id`, `start_date`, `end_date`, `name`. Multiple per breakdown. Excluded from teaching-day derivation everywhere (admin display + teacher projection).
- **Exam-Period Dates** — the set of individual dates expanded from a breakdown's Exam Periods, unioned into the holiday set passed to `compute_teaching_days`. The mechanism by which an Exam Period removes teaching days.
- **Formative Assessment slot** (**FA slot**) — an Assessment Slot with `assessment_type='formative'`, emitted by the Intelligent Chapter Planner as a `PlanUnit` with `slot_type='formative_assessment'`, persisted into `class_assessment_slots`.
- **Default FA Config** — the per-subject default Question Config applied to FA slots when generating their exam (no per-slot config UI in this feature). Constant `DEFAULT_FA_CONFIG[subject]`.
