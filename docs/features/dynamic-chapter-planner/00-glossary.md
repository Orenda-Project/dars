# Glossary — Dynamic Chapter Planner

Future docs may only use terms defined here. Add new terms as they emerge.

- **Live plan** — the per-CST realized slot sequence (`class_lesson_slots` +
  `class_assessment_slots`). The single source of truth for what a class teaches and when.
  Distinct from the **Syllabus Breakdown**, which only *seeds* it once.

- **Syllabus Breakdown** — the org-wide template (`syllabus_breakdowns` +
  `syllabus_chapters`, plus `breakdown_holidays` / `exam_periods`). Read once at
  break-it-down to seed a CST's live plan; thereafter consulted only for holiday/exam
  dates (which the projector reads live).

- **Position** — the single integer ordering shared across BOTH slot tables per CST
  (`UNIQUE (cst_id, position)` on each; the projector merges them by position). 1 slot =
  1 teaching day.

- **Projection** — turning position-ordered slots into dates at read time
  (`projector.project_cst_schedule`) by walking teaching days minus holidays. Dates are
  never stored.

- **Overflow** — `ProjectedSlot.is_overflow=True`: a tail slot has no teaching day left in
  the academic year. The signal that a class is genuinely behind; surfaces a human alert.

- **Mandatory slot** — a non-droppable lesson/FA that teaches required content.

- **Flex slot** — a droppable lesson slot (revision / consolidation), tagged `flex=true`.
  The interleaved buffer. Consumed first when a reteach is needed, so the tail doesn't shift.

- **Mandatory budget** — the number of teaching days a chapter's mandatory content is
  planned into = `round(chapter_teaching_days * completion_target)`.

- **Completion target** — the fraction of teaching days reserved for mandatory content
  (~0.7–0.8). A knob (org default + optional per-CST override). Lower = more buffer.

- **Shared remainder pool** — the thin slack left after per-chapter flex (rounding leftovers
  + end-of-term), placed at the end; covers cross-chapter summative reteach.

- **Taught-lock** — the invariant that no mutation may touch a slot at or before the CST's
  last `taught`/`completed` position. Only future `planned`/`scheduled` slots may move.

- **Reteach** — re-covering a sub-SLO the class failed. Lightweight (fold into next class /
  mark needs-rework) by default; heavy (consume a flex slot, else insert a new slot) on
  teacher confirmation.

- **Reteach trigger** — `sub_slo_mastery.mastery_percent` below `RETEACH_MASTERY_THRESHOLD`
  surfaces a suggestion badge on the FA slot. Never auto-applied.

- **origin** — provenance of a class slot: `'breakdown'` (seeded), `'reteach'`, `'manual'`.

- **consume-flex** — repurpose the nearest downstream flex slot in place for a reteach
  (no position shift) instead of inserting a new slot.

- **Overflow consequence** — the year-end impact of a reteach INSERT (D-17): which tail slots
  newly **overflow** because the inserted slot shifted them past the academic year's last
  teaching day. Computed as a projector dry-run delta (the overflow set before vs after the
  insert). `consume-flex` and the lightweight path shift nothing, so their consequence is
  always empty.

- **Completion target** (concrete home, D-14) — the org column
  `organizations.default_completion_target NUMERIC DEFAULT 0.80`: the fraction of a chapter's
  teaching days reserved for mandatory content. Org default only — no per-CST override.
