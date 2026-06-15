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

## Notes from execution

**F-3.1 / F-3.2 (backend)** shipped in PR #143. **F-3.3 (teacher-app surface)** built
2026-06-15 (bead `feat-dynamic-planner-reteach-ui`, branch `feat/dynamic-planner-reteach-ui-wt`,
awaiting PR merge):

- **Where it lives (D-18):** on the mastery-entry/results page
  (`webapp/app/teacher-app/classes/[cst_id]/assessments/[slot_id]/results/page.tsx`), not a
  separate FA-timeline badge. The suggestion is only meaningful post-grading, and grading
  happens here. The panel renders inline after a successful `submitExamResults`, and the page
  also re-fetches the suggestion on load when the slot is already `completed` (so a returning
  teacher still sees it). When there is no suggestion (or empty items), behaviour is unchanged
  — it auto-navigates back to the assessments tab as before; when there *is* one, it stays so
  the teacher can act.
- **Component:** `webapp/components/molecules/reteach-panel.tsx` — a presentational molecule
  (hook-free; the page owns the suggestion data + the per-sub-SLO state machine + the API
  calls, mirroring `mastery-entry-template`). The "Reteach" badge + heading reads "Class
  struggled with N sub-SLO(s) — reteach?" and lists each below-threshold sub-SLO with its
  code, statement, and rounded mastery %.
- **Confirm step (D-9, never auto-applies):** each sub-SLO offers two radio modes with
  **lightweight pre-selected** ("Re-cover in your next class" — flips coverage, no slot/shift)
  and **heavy** ("Add a reteach lesson" — consumes a spare revision day if available, else
  inserts a new day). Confirm calls `slots.confirmReteach({ sub_slo_id, mode })`; "Not now"
  dismisses and leaves the plan untouched. After acting, the row shows the outcome and disables
  further action on that sub-SLO.
- **Overflow consequence, made legible (D-18):** outcomes are phrased as calendar outcomes, not
  raw `OverflowConsequence` integers. `path==='lightweight'` → flagged for rework, schedule
  unchanged. `path==='consume_flex'` → "added using a spare revision day — your schedule is
  unchanged." `path==='insert'` with `newly_overflowed_positions.length===0` → "added on a new
  day — everything still fits." `path==='insert'` with overflow → "pushed N later lesson(s)
  past the end of the school year, starting at lesson #`first_overflow_position`; drop a
  revision day, move an exam, or trim coverage to fit it back in."
- **Contract note:** the shipped client methods are `slots.getReteachSuggestion` /
  `slots.confirmReteach` (the `slots` namespace in `webapp/lib/dars-api.ts`), not `mastery.*`.
  The UI consumes the contract exactly as shipped — no `dars-api.ts` or backend change.
- **Validation:** `npx tsc --noEmit` clean, `eslint` clean on both changed files,
  `next build` clean (27 routes, the results route compiled).
