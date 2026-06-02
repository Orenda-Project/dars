# Glossary — Syllabus Breakdown & Teacher Chapter Plan

Inherits the v2 rebuild glossary. Terms specific to this re-architecture:

| Term | Definition |
|---|---|
| **Syllabus Breakdown** | The renamed, slimmed former "Chapter Breakdown". The **only** admin/global artifact: an ordered set of chapters, each with an explicit calendar **date range** (`start_date`/`end_date`). No slots. Dars-owned, **global scope only**. Answers "which chapter is taught when". |
| **Chapter Plan** | The breakdown of **one chapter** into a sequence of slots (lessons + assessments). Now a **teacher-only** action in the teacher app — not an admin artifact. Generated on demand via "break it down". Stored per-class in `class_lesson_slots` / `class_assessment_slots`. |
| **Period** | One teaching session for a class on a given weekday, represented by a `timetables` row (`cst_id`, `day_of_week`). **Periods/week** = count of timetable rows for the CST (default Mon–Fri = 5 if none set). |
| **Slot-count formula** | How many slots a chapter's Chapter Plan gets: `periods_per_week × weeks_in_chapter_range`, where weeks are derived from the chapter's Syllabus Breakdown date range. E.g. 5 periods/week × 4 weeks = 20 slots. (D-9) |
| **Break it down** | The teacher-app action on a chapter: computes the slot count via the formula, generates that many lesson+assessment slots (reusing the salvaged planner), writes them to the class slot tables, and lets the teacher edit. |
| **Position by today** | The teacher app highlights which chapter the class "should be on" by comparing today's date to the Syllabus Breakdown date ranges. |
| **Class slot tables** | `class_lesson_slots`, `class_assessment_slots`, `class_assessment_slot_topics` — **kept**, but now populated by the teacher's break-it-down action instead of by realization from `breakdown_slots`. |
| **Data bank** | Super-admin-owned reference content that is **NOT touched** by this feature: curriculums, grades, subjects, slos, sub_slos, books, book_chapters, topics, and their mappings. Plus the global Syllabus Breakdowns themselves. |
| **Removed concepts** | `breakdown_slots`, `breakdown_slot_topics`, org/class breakdown scope, fork chain, auto-build (whole-book), per-chapter seed, realization (`realize_service`). All deleted (D-2, D-3, D-5). |
