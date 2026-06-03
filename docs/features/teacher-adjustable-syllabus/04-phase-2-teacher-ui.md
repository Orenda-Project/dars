# Phase 2 — Teacher-app UI: recommend → pick → date → reorder → break down

The teacher-facing surface for Action 1 (build the chapter path) feeding into the existing
break-it-down (Action 2). One PR → staging (frontend + read-shape glue).

**Bead:** `feat-teacher-adjustable-syllabus-phase-2-ui`
**Depends on:** Phase 1 merged.

---

## F2.1 — Recommendation prompt (empty path)

**Spec.** On the Syllabus tab, when the class path is empty, show:
*"Nothing planned yet. The default syllabus suggests **Chapter N: <title>** — what would
you like to teach?"* with the recommended chapter highlighted and a way to pick **any**
chapter from the book. (Uses the Phase 1 `GET /csts/{id}/syllabus` path + `recommended_next`.)

**Acceptance.** Fresh class shows the prompt with the global's recommendation; teacher can
pick the recommended chapter or any other.

## F2.2 — The class path: pick, set dates

**Spec.** Render the class path (ordered by position) — each chapter row: title, editable
date range, `slot_count`. A "recommended next" affordance to append the suggested chapter.
Picking calls `POST /chapters`; editing dates calls `PATCH /chapters/{id}`; re-fetch after.

**Acceptance.** Path lists chosen chapters in order. Adding the recommended chapter appends
it. Editing dates persists + recomputes slot_count.

## F2.3 — Reorder chapters

**Spec.** Reorder chapters in the path (up/down or drag) → `PUT /chapters/order`. If the
Phase-1 status-lock (F1.5) is in, in-progress/done chapters show locked (no handle) and a
rejected reorder surfaces the 422; if status-lock was cut, all chapters reorder freely.

**Acceptance.** Teacher reorders chapters; the order persists and the Today "current
chapter" (by date) reflects path order. (If lock is in: a started chapter can't be moved.)

## F2.4 — Break it down

**Spec.** Per chapter (once dated), a **"Break it down"** button → calls the existing
`/plan` (Action 2, F1.6) → the chapter's generated lessons appear in Timeline/Today (this
feature does not dictate LP/assessment content — `intelligent-chapter-planner` owns that).
Disable when no dates ("set dates first") or already broken down (existing 422s).

**Acceptance.** Dating + breaking down a chapter generates its plan and surfaces it in the
existing Timeline/Today views. No regression to the shipped break-it-down behavior.

## F2.5 — (Optional) status badges

**Spec.** *Only if Phase 1 F1.5 shipped.* Show each chapter's status badge (Yet to start /
In progress / Done) on its row.

**Acceptance.** Badges reflect taught progress; omitted cleanly if status wasn't built.

---

## Notes from execution
_(append during implementation; don't alter specs)_
