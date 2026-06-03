# Phase 3 — Teacher-app UI: suggestion → pick → plan → break down

The teacher-facing surface for the whole flow. One PR → staging (frontend + read-shape
glue).

**Bead:** `feat-teacher-adjustable-syllabus-phase-3-ui`
**Depends on:** Phase 2 merged.

---

## F3.1 — Empty-state suggestion prompt

**Spec.** On the Syllabus tab, when the class path is empty, show:
*"Nothing planned yet. The default syllabus suggests **Chapter 1: <title>** — what would
you like to teach?"* with the recommended chapter highlighted and a way to pick **any**
chapter from the book. (Uses F1.4 path + recommendation.)

**Acceptance.** Fresh class shows the prompt with the global's Ch 1 recommended; teacher
can pick Ch 1 or any other.

## F3.2 — The class path with chapter statuses

**Spec.** Render the class path (ordered) — each chapter row shows: title, date range
(editable), **status badge** (Yet to start / In progress / Done), and slot_count. A
"recommended next" affordance to add the suggested chapter to the path. Picking adds it
(F1.5).

**Acceptance.** Path lists chosen chapters in order with correct status badges. Adding the
recommended chapter appends it. Editing dates persists + recomputes slot_count.

## F3.3 — Break it down → show the LPs

**Spec.** Per chapter (once dated), a **"Break it down"** button → calls Action 2 → the
chapter's **lesson plans** appear (in Timeline/Today, lessons-only per D-8). Show the
generated LP list. Disable when no dates ("set dates first") or already broken down.

**Acceptance.** Dating + breaking down a chapter shows the LPs the teacher would teach;
no assessment rows appear; status stays yet_to_start until something's taught.

## F3.4 — Reorder upcoming; lock taught

**Spec.** Allow reordering **yet-to-start** chapters (up/down or drag); in-progress/done
chapters are visually locked (no reorder handle). Reorder calls F2.1; a rejected reorder
(touching a locked chapter) surfaces the 422 message.

**Acceptance.** Teacher reorders two upcoming chapters; an in-progress chapter can't be
moved. Today's "current chapter" reflects the path order.

---

## Notes from execution
_(append during implementation; don't alter specs)_
