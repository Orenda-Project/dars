# Phase 3 — Reteach trigger

Turn a failed formative assessment into a teacher-confirmed reteach that consumes flex (no
shift) or inserts a slot (shift, with the year-end consequence shown). Teacher-initiated only
(D-9).

## F-3.1 — Mastery threshold + suggestion signal

**Spec:** constant `RETEACH_MASTERY_THRESHOLD` (start 60.0). A read that, for a graded FA
slot, returns the sub-SLOs whose `sub_slo_mastery.mastery_percent` is below threshold — the
suggestion payload for the teacher app (a badge on the FA slot). No mutation here.
**Acceptance:** a CST with a below-threshold sub-SLO surfaces it against the right FA slot;
above-threshold surfaces nothing.

## F-3.2 — Reteach actions

**Spec:** on teacher confirmation, two paths:
- **Lightweight (default):** mark the sub-SLO needs-rework (flip `cst_sub_slo_coverage`); no
  new slot. For the fold-into-next-class case.
- **Heavy:** `consume_flex_slot` for the nearest downstream flex slot (no shift); if none,
  `insert_lesson_slot` (shift) — and the response includes the **overflow consequence**
  (does this push a tail slot out of the year? which one?). Then generate the LP via
  `get_or_generate_lp` with `lp_type='revision'`, `origin='reteach'`,
  `reteach_for_sub_slo_id` (D-10).
**Acceptance:** lightweight flips coverage only; heavy consumes flex when available (positions
unchanged) and inserts + reports consequence when not; the reteach slot gets an LP on the
existing path.

## F-3.3 — Teacher-app surface

**Spec:** badge on the FA slot card ("class struggled with X — reteach?"), a confirm step that
shows the consequence (which flex day is used / what falls off), and the two action choices.
Reteach is never auto-applied.
**Acceptance:** the badge appears only post-grading below threshold; confirming runs the chosen
action; declining leaves the plan untouched.

## F-3.4 — Tests

**Spec:** threshold read returns correct sub-SLOs; consume-vs-insert branch picks correctly;
consequence reporting flags overflow when the insert pushes past year-end.
**Acceptance:** green; mutation tests sqlite-runnable.

## Dependencies

Depends on Phase 1 (mutation primitives + `reteach_for_sub_slo_id`) and Phase 2 (flex slots to
consume). Reuses shipped `get_or_generate_lp` (#133) and `mastery_service` / `sub_slo_mastery`.
