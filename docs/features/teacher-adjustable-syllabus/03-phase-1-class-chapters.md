# Phase 1 — Class chapter path (backend): pick, date, reorder, recommend

All of Action 1's backend. Introduces `class_chapters` (the class's own teaching path) and
the endpoints to build/edit it, plus the "recommended next" suggestion from the global.
One PR → staging.

**Bead:** `feat-teacher-adjustable-syllabus-phase-1-class-chapters`
**Depends on:** nothing (additive; builds on shipped syllabus + class slots).

---

## F1.1 — Schema: `class_chapters`

**Spec.** Migration `20260603100000_class_chapters.sql` per `02-data-model.md`. Validate
against staging in a rolled-back transaction before merge.

**Acceptance.** Table exists with both unique constraints + org/cst cascades. Non-DB suite green.

## F1.2 — Path service: list / pick / set-dates / remove / reorder

**Spec.** New `class_chapter_service.py`:
- `list_class_path(conn, cst_id)` → chapters ordered by `position`, with dates +
  `slot_count` (real teaching periods in the chapter's date range, via the existing
  `chapter_slot_count`) + **status** (D-4; see F1.5 — optional but cheap to derive).
- `pick_chapter(conn, cst_id, org_id, book_chapter_id)` → insert at next `position` (end).
  422 if already in path (unique constraint). Undated (D-7).
- `set_chapter_dates(conn, cst_id, book_chapter_id, start, end)` → set the row's dates.
- `remove_chapter(conn, cst_id, book_chapter_id)` → delete the path row. (Does NOT touch
  generated class slots.) If status-lock (F1.5) is in, reject removing a started chapter.
- `reorder_path(conn, cst_id, ordered_book_chapter_ids)` → rewrite `position` 1..N in one
  transaction. (Lock rule optional — see F1.5.)

**Acceptance.** Pick Ch1 then Ch3 → 2-chapter path in order. Set dates → persists. Reorder
to [Ch3,Ch1] → positions rewritten. Remove → row gone, slots untouched.

## F1.3 — Recommended next (D-3)

**Spec.** `recommended_next_chapter(conn, cst_id)` → the global default's lowest-position
chapter not already in the class path (empty path → global's first). Returns
book_chapter_id + label, or None if the path already covers the global.

**Acceptance.** Empty path recommends the global's Ch 1. After picking Ch 1, recommends the
global's next chapter (by global order).

## F1.4 — Endpoints (teacher-scoped, tenancy enforced)

**Spec.**
- `GET /csts/{cst_id}/syllabus` — **rework** the shipped endpoint to return: the class
  path (chapters: book_chapter_id, position, dates, slot_count, status) + `recommended_next`
  + `periods_per_week`. Empty path → `[]` + recommendation.
- `POST /csts/{cst_id}/chapters` `{ book_chapter_id }` → pick.
- `PATCH /csts/{cst_id}/chapters/{book_chapter_id}` `{ start_date?, end_date? }` → set dates.
- `PUT /csts/{cst_id}/chapters/order` `{ book_chapter_ids: [...] }` → reorder.
- `DELETE /csts/{cst_id}/chapters/{book_chapter_id}` → remove.

**Acceptance.** Full pick→date→reorder→remove cycle works via the API; a CST outside the
caller's org 404s on every endpoint.

## F1.5 — (Optional polish) chapter status + reorder lock

**Spec.** *Not blocking — ship F1.1–F1.4 even if this is cut.* Derive chapter **status**
(yet_to_start / in_progress / done) from the CST's generated slots for the chapter (D-4)
and include it on `list_class_path`. If included, make `reorder_path`/`remove_chapter`
reject moving/removing a chapter whose status ≠ yet_to_start (D-6 — the past is locked).

**Acceptance (if included).** A chapter with a taught slot reads `in_progress` and cannot
be reordered/removed; yet_to_start chapters reorder freely. If cut: reorder/remove are
unrestricted and status is omitted from the response.

## F1.6 — Break-it-down reads class-path dates (D-5)

**Spec.** `generate_chapter_plan` currently reads the chapter's date range from
`syllabus_chapters` (the global). Point it at the CST's `class_chapters` row for that
`book_chapter_id`. 422 if the chapter isn't in the class path, has no dates, or already has
generated slots (existing guard). **No change to what it generates** (D-8 — that's
`intelligent-chapter-planner`'s domain).

**Acceptance.** Break-it-down on a dated class-path chapter generates slots sized by the
class-path date range. On a chapter not in the path → 422 ("add it to your plan first").

---

## Notes from execution
_(append during implementation; don't alter specs)_
