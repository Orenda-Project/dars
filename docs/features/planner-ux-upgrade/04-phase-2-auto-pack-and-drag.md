# Phase 2 — Anchor-date auto-pack + drag-to-reorder

**Goal:** kill the two pain points the user named. The teacher sets one anchor
date and the planner auto-packs every yet-to-start chapter back-to-back from
there; reordering becomes drag-and-drop that re-flows downstream dates. Manual
per-chapter date entry stays as the escape hatch.

**Builds on Phase 1:** reuses the holiday set (for packing around non-teaching
days) and the warning helper (to flag any overlap the teacher's manual edits
still create). Independently shippable: after this phase the planner is the new
scheduler; Phase 1's holiday hints and warnings remain.

**Constraints inherited (do not violate):**
- D-6 (this folder) / D-6 (`teacher-adjustable-syllabus`): locked
  (in_progress/done) chapters never move and are never repacked. Packing starts
  after the last locked chapter.
- D-2: no schema change, no new endpoint — orchestrate `setChapterDates` (PATCH)
  and `reorderChapters` (PUT) only.
- D-7: multi-chapter repack = sequential PATCHes behind one busy state, single
  refetch at the end.

---

## F2.1 — Anchor date + "Auto-pack term" action

**Spec.** In EDIT mode, add an anchor control at the top of the path:

- A single date input labelled "Term starts" / "Pack from". Defaults to: the day
  after the last locked chapter's `end_date` if any chapter is locked; else the
  earliest existing `start_date` in the path; else today.
- An "Auto-pack chapters" button. On click, compute consecutive date ranges for
  every yet-to-start chapter in current `position` order, starting at the anchor:
  - chapter K's `start_date` = the next teaching day on/after the running cursor
    (skip weekends + effective holidays so a chapter never *starts* on a
    non-teaching day);
  - chapter K's `end_date` = the calendar date by which the chapter has
    accumulated its required teaching periods. **Period count source:** the
    chapter's current `slot_count` when it has dates; for an undated chapter, use
    its org-breakdown `derived_teaching_days`, else a 5-period (one-week) default
    (D-9, resolves O-1). Fetch the breakdown once via
    `SyllabusForCstResponse.syllabus_breakdown_id` → `breakdowns.getBreakdown(id)`
    → `chapters[].derived_teaching_days` keyed by `book_chapter_id`.
  - running cursor for chapter K+1 = the next teaching day after K's `end_date`
    (no gap, no overlap by construction).
- Persist via F2.4's sequential-PATCH runner; refetch once.

**Acceptance.**
- With no chapter locked, clicking Auto-pack from anchor A dates every chapter
  consecutively starting at A, with no overlaps and no teaching-day gaps between
  consecutive chapters (verify with the Phase-1 warning helper: zero overlap/gap
  warnings after a clean pack).
- With a chapter locked (in_progress/done), its dates are untouched and packing
  resumes the day after it; the locked chapter is not in the PATCH set.
- No chapter starts on a weekend or effective holiday.
- The action is one busy cycle; the path renders once at the end.

**Dependencies:** F2.4, Phase 1 holiday set.

---

## F2.2 — Drag-to-reorder with downstream re-flow

**Spec.** Replace the ▲▼ buttons' role as the *primary* reorder affordance with
drag-and-drop using `@dnd-kit/sortable` (D-8). Keep keyboard reorder as the
accessible fallback (dnd-kit's keyboard sensor, or retain ▲▼ for a11y).

- Only yet-to-start rows get a drag handle; locked rows render with a 🔒 (as
  today) and are not sortable. dnd-kit's sortable list excludes them or treats
  them as a fixed prefix.
- On drop:
  1. Submit the new order to `reorderChapters` (PUT) — the server enforces the
     D-6 lock and returns the updated path.
  2. Then re-flow dates: re-pack the yet-to-start tail from the same anchor
     logic as F2.1 so the dropped chapter and everything after it get
     consecutive dates. (Reorder alone changes `position`; re-flow keeps dates
     consistent with the new order — D-5: downstream only.)
- During the drag, show a live preview (dnd-kit overlay) of the row moving;
  commit only on drop.

**Acceptance.**
- Dragging a yet-to-start chapter to a new slot persists the new order and
  re-dates the affected tail with no overlaps.
- Attempting to drag a locked chapter is impossible (no handle); dragging a
  yet-to-start chapter *above* a locked one is rejected/clamped (the server's
  D-6 validate_reorder would 422 — the UI prevents it by treating locked rows as
  a fixed prefix, and on any 422 it re-syncs from the server per the existing
  `runPathMutation` catch).
- Keyboard users can still reorder (dnd-kit keyboard sensor or ▲▼ retained).
- Touch drag works on a tablet (pointer/touch sensors configured).

**Dependencies:** F2.1 (re-flow reuses the pack logic), F2.4.

---

## F2.3 — Manual override stays; re-flow respects a pinned edit

**Spec.** Keep the per-chapter date inputs (Phase-1 untouched) as the escape
hatch. When a teacher manually edits a chapter's start or end:

- Persist that bound (existing onBlur → `setChapterDates`).
- Re-flow the yet-to-start chapters *after* the edited one from the edited
  chapter's new `end_date` (D-5: downstream only; earlier chapters untouched).
- If the manual edit overlaps an *earlier* chapter, do not auto-resolve — let
  the Phase-1 overlap warning surface it (D-4/D-5).

**Acceptance.**
- Editing a chapter's start date re-dates the chapters after it consecutively;
  chapters before it keep their dates.
- A manual edit that overlaps an earlier chapter shows the overlap warning and
  still saves (non-blocking).

**Dependencies:** F2.1, Phase 1 warnings.

---

## F2.4 — Sequential repack runner (PATCH batching behind one busy state)

**Spec.** Extend the page's `runPathMutation` (or add a sibling
`runPathRepack`) to accept a computed list of per-chapter date patches and:

- Issue them **sequentially** (await each `setChapterDates` before the next) so
  the server's `position`/`slot_count` recompute stays coherent (D-7).
- Hold `pathBusy` for the whole batch; set the final returned syllabus once at
  the end (or refetch once via `loadSyllabus`).
- On any failure mid-batch, stop, surface the error, and re-sync from the server
  (mirror the existing `runPathMutation` catch behaviour) so the UI reflects
  persisted state.

**Acceptance.**
- Auto-packing N chapters fires N PATCHes in order, shows one spinner, and
  renders the final path once.
- A mid-batch 422 leaves the path in the server's actual state (re-fetched), not
  a half-applied client guess.

**Dependencies:** D-2, D-7.

---

## Open questions

- **O-1: Default span for an UNDATED chapter during auto-pack.** ✅ RESOLVED
  2026-06-19 → **D-9**: use the chapter's org-breakdown `derived_teaching_days`
  when available (option a), else a 5-period one-week default (option b). See D-9
  for the reachability path and F2.1's updated spec.

---

## Notes from execution

_(Append findings, scope changes, and follow-ups here during the build. Do not
rewrite the specs above.)_
