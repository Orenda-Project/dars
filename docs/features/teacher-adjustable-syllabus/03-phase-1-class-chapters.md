# Phase 1 — Class chapter path: pick, status, recommendation (backend)

The core of Action 1. Introduces `class_chapters` (the class's own teaching path), the
pick/list endpoints, derived chapter status, and the "recommended next" suggestion from
the global. One PR → staging.

**Bead:** `feat-teacher-adjustable-syllabus-phase-1-class-chapters`
**Depends on:** nothing (additive; builds on shipped syllabus + class slots).

---

## F1.1 — Schema: `class_chapters`

**Spec.** Migration `20260603100000_class_chapters.sql` per `02-data-model.md`. Validate
against staging in a rolled-back transaction before merge.

**Acceptance.** Table exists with both unique constraints + org/cst cascades. Non-DB suite green.

## F1.2 — Path service: list + pick + remove

**Spec.** New `class_chapter_service.py` (or extend `chapter_plan_service.py`):
- `list_class_path(conn, cst_id)` → chapters ordered by `position`, each with derived
  status (D-4) + dates.
- `pick_chapter(conn, cst_id, org_id, book_chapter_id)` → insert a `class_chapters` row at
  the next `position` (end of path). Idempotent-ish: 422 if the chapter is already in the
  path (unique constraint). Undated (D-7).
- `remove_chapter(conn, cst_id, book_chapter_id)` → delete the path row **only if its
  status is yet_to_start** (D-6 lock); else 422. (Does not touch generated slots.)

**Acceptance.** Picking Ch 1 then Ch 3 yields a 2-chapter path in pick order. Removing a
yet-to-start chapter works; removing an in-progress one is rejected.

## F1.3 — Recommended next (D-3)

**Spec.** `recommended_next_chapter(conn, cst_id)` → the global default's lowest-position
chapter not already in the class path (empty path → global's first). Returns the
book_chapter_id + label, or None if the path already covers the syllabus.

**Acceptance.** Empty path recommends the global's Ch 1. After picking Ch 1, recommends
the global's next chapter (by global order).

## F1.4 — Surface path + recommendation on the teacher syllabus endpoint

**Spec.** Rework `GET /csts/{cst_id}/syllabus` (the Phase-1-shipped endpoint) to return:
the **class path** (chapters with position, dates, derived status, slot_count) + the
**recommended next** chapter + `periods_per_week`. When the path is empty, the response
makes clear "nothing planned yet" + the recommendation. Keep it backward-tolerant for the
teacher app (Phase 3 consumes the new shape).

**Acceptance.** A CST with an empty path returns `[]` chapters + a recommendation of the
global Ch 1. After picking + dating a chapter, it appears in the path with status
`yet_to_start` and a computed slot_count.

## F1.5 — Pick / set-dates endpoints

**Spec.** Teacher-scoped (tenancy enforced):
- `POST /csts/{cst_id}/chapters` body `{ book_chapter_id }` → pick (F1.2).
- `PATCH /csts/{cst_id}/chapters/{book_chapter_id}` body `{ start_date?, end_date? }` → set
  the path row's dates (D-7).
- `DELETE /csts/{cst_id}/chapters/{book_chapter_id}` → remove (yet-to-start only).

**Acceptance.** Pick → date → appears with a slot_count derived from the dates + timetable.
Tenancy: a CST outside the caller's org 404s.

---

## Notes from execution
_(append during implementation; don't alter specs)_
