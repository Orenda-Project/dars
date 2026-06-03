# Phase 2 — Reorder (lock taught) + break-it-down on the class path + LPs-only

Completes Action 1 (reorder upcoming, with locking) and points Action 2 (break-it-down)
at the class path, with assessments dropped. One PR → staging.

**Bead:** `feat-teacher-adjustable-syllabus-phase-2-reorder-breakdown`
**Depends on:** Phase 1 merged.

---

## F2.1 — Reorder upcoming chapters (D-6)

**Spec.** `PUT /csts/{cst_id}/chapters/order` body `{ book_chapter_ids: [...] }` — rewrite
`class_chapters.position` to the given order in one transaction. **Reject (422) if the
reorder would move any in-progress/done chapter** (their relative order among themselves
must be preserved and they must stay ahead of yet-to-start chapters — i.e. only the
yet-to-start tail is freely reorderable). Simplest enforcement: the submitted order must
keep all non-yet-to-start chapters in their current relative positions at the front.

**Acceptance.** With Ch1 in-progress + Ch2,Ch3 yet-to-start, reordering to [Ch1,Ch3,Ch2]
succeeds; reordering to [Ch3,Ch1,Ch2] (moving the in-progress Ch1) 422s. Positions stay
unique/contiguous.

## F2.2 — Break-it-down reads class-path dates (D-5)

**Spec.** `generate_chapter_plan` currently reads the chapter's date range from
`syllabus_chapters` (the global). Change it to read from the CST's `class_chapters` row
for that `book_chapter_id`. 422 if the chapter isn't in the class path, or has no dates,
or already has generated slots (existing guard).

**Acceptance.** Break-it-down on a dated class-path chapter generates slots sized by the
class-path date range. Break-it-down on a chapter not in the path 422s ("add it to your
plan first").

## F2.3 — Lessons only (D-8 / D-9)

**Spec.** Per D-9 (confirm scope with user before coding):
- **Default (D-9a, generation-only):** in `generate_chapter_plan`, filter the planner's
  `PlannedSlot` list to lessons + revision before insert; do **not** insert any
  `class_assessment_slots`. Every teaching period becomes a lesson plan. Log how many
  assessment slots were suppressed.
- **(D-9b, full teardown — only if user picks it):** additionally strip assessment slots
  from timeline/today/mark-complete + remove the tables/UI. Larger; separate sub-tasks.

**Acceptance (D-9a):** Breaking down a 20-period chapter creates 20 lesson slots, 0
assessment slots. Timeline/Today show lessons only. No 500s.

## F2.4 — Chapter status reflects break-it-down + teaching

**Spec.** Confirm the derived status (D-4) transitions correctly: yet_to_start (picked,
or broken down but nothing taught) → in_progress (≥1 taught) → done (all taught/skipped).
Ensure `list_class_path` recomputes after break-it-down and after mark-taught.

**Acceptance.** Pick+date+break-down → still yet_to_start (nothing taught). Mark one
lesson taught → in_progress. Mark all → done.

---

## Notes from execution
_(append during implementation; don't alter specs)_
