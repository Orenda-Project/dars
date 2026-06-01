# Glossary

- **Class detail page** — `/teacher-app/classes/[cst_id]`. The per-class page in
  the teacher sample app. Currently a tab bar (Lessons / Assessments / Timetable
  / Book / SLO Progress) defaulting to Lessons.
- **CST** — class-subject-teacher row. The unit a teacher teaches: one class ×
  one subject. `cst_id` is the route param.
- **Today tab / Today dashboard** — the new default tab introduced by this
  feature. A single-class overview of today's work + progress.
- **Today slot** — the lesson slot OR assessment slot scheduled for the class
  today, from `GET /api/v2/today` (the `TodayEntry` whose `cst_id` matches).
  May be neither (no class today / holiday), a lesson, or an assessment.
- **Covered / Now / Next** — the progress strip. *Covered* = lesson slots with
  `status: "taught"`. *Now* = today's slot (or the next planned slot if nothing
  is scheduled today). *Next* = the planned slot following Now.
- **Progress %** — share of sub-SLOs with coverage `status: "taught"` over the
  total in scope, from `GET /class-subject-teachers/{cst_id}/sub-slo-coverage`.
- **anchor_date** — the calendar date a slot is scheduled for (may be null for
  unscheduled/overflow slots).
