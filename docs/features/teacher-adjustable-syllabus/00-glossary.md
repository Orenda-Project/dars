# Glossary — Teacher-Adjustable Syllabus (suggestion-led)

Inherits the `syllabus-breakdown-and-teacher-chapter-plan` glossary. New/changed terms:

| Term | Definition |
|---|---|
| **Default syllabus** | The published **global** Syllabus Breakdown for a (curriculum, grade, subject). Dars-owned. Now purely **advisory** — it *suggests*, it does not bind. |
| **Class path** | The class's own ordered list of chapters it is teaching, stored in `class_chapters` (per CST). The source of truth for what a class teaches and in what order. |
| **`class_chapters`** | New per-CST table: `(cst_id, book_chapter_id, position, start_date, end_date, …)`. One row per chapter the teacher has added to the class path. |
| **Chapter status** | Derived per chapter from its generated class slots: **yet-to-start** (no slots, or no terminal slots), **in-progress** (some terminal), **done** (all slots terminal). "Terminal" = taught/completed/skipped. (D-4) |
| **Suggestion / recommended next** | The chapter the global default implies the class should teach next (by global position / date), surfaced as a recommendation. The teacher may pick it or any other chapter. (D-3) |
| **Pick a chapter** | Action that **records** a chapter into the class path (`class_chapters` row). Distinct from breaking it down. (D-2) |
| **Action 1 — Decide the syllabus** | The teacher builds their class path: accept the recommended order from the global, or pick/reorder/date chapters themselves. This feature's main new surface. |
| **Action 2 — Break it down** | The already-shipped `/plan` flow (`generate_chapter_plan`), reused unchanged: for a chapter in the path it generates that chapter's plan, sized by the period count. This feature only points it at a class-path chapter — **what it generates (LPs/assessments) is `intelligent-chapter-planner`'s domain, D-8.** (D-5) |
| **`position`** | Teaching order within the class path (`class_chapters.position`). Reorderable for **upcoming** (yet-to-start) chapters only. |
| **Lock** | In-progress / done chapters cannot be reordered or removed; their taught history is immutable. (D-6) |
| **Period count** | Teaching periods available for a chapter = `len(compute_teaching_days(chapter date range, the CST's timetable weekdays, holidays))`. Drives Action 2's slot count. (Inherited from the shipped feature, D-9 there.) |
| **Auto-seed** | On a class's first syllabus read, `seed_class_chapters_from_breakdown` copies the org's **published** breakdown chapters (book_chapter_id, position, start_date, end_date) into `class_chapters` for that CST — idempotent, clean-install only (skips if the path already has rows). Added by `teacher-readonly-syllabus`; **kept** in the revival (D-10). The class path therefore starts as a per-class *copy* of the org breakdown that the teacher then edits. |
| **Read-only reversal** | The `teacher-readonly-syllabus` feature (PRs #130/#131, 2026-06-03) that removed this feature's mutation layer and made the class syllabus tab read-only. Reversed by the revival (D-9). |
| **Revival** | The 2026-06-15 reopening of teacher editing (D-9…D-12): restore #109's pick/set-dates/reorder/remove on top of today's auto-seeded, expandable syllabus tab. |
