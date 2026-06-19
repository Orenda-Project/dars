# Glossary — Planner UX Upgrade

Future docs in this folder may only use terms defined here. Add new terms as
they emerge during execution.

## Surfaces

- **Planner** — the **Edit syllabus** mode of the teacher-app Syllabus tab
  (`/teacher-app/classes/{cst_id}?tab=syllabus`). In VIEW mode the tab shows a
  settled plan (dates as plain text, chapter rows link to the Chapter Page); in
  EDIT mode it reveals the date / reorder / add / remove affordances. This
  feature changes the EDIT-mode affordances only.
- **Path / Class path** — the ordered list of chapters this class will teach,
  one row per chapter in the `class_chapters` table, ordered by `position`.
  Auto-seeded from the org breakdown (D-10 of `teacher-adjustable-syllabus`),
  then teacher-edited. Synonym: *teaching path*.
- **Path row** — one chapter in the path. Carries `book_chapter_id`,
  `position`, `start_date`, `end_date`, `slot_count`, `is_generated`, `status`.

## Concepts introduced by this feature

- **Anchor date** — the single date the teacher sets to start auto-packing from:
  the term/first-chapter start. Auto-pack flows every yet-to-start chapter
  forward from here. Not a stored column — it's just the `start_date` the
  teacher gives the first packable chapter; "anchor" is the UI framing.
- **Auto-pack** — compute consecutive date ranges for all yet-to-start chapters
  so chapter N+1 starts on the next teaching day after chapter N ends, each
  chapter spanning enough calendar days to contain its period count. Persisted
  by issuing `setChapterDates` per affected chapter. Locked chapters (D-6) are
  never repacked; packing resumes after the last locked chapter.
- **Re-flow** — after a drag-reorder (or a manual date edit), recompute the
  downstream chapters' dates so the path stays consecutive. Same machinery as
  auto-pack, applied to the chapters after the change point.
- **Manual override** — a per-chapter explicit date edit (the escape hatch).
  Pins that chapter's range; re-flow treats a manually-pinned start as a fixed
  point to pack the rest around. (For v1, manual override simply re-packs
  downstream from the edited chapter — see D-5.)
- **Locked chapter** — a path row with status `in_progress` or `done` (D-6 of
  `teacher-adjustable-syllabus`): its dates and position are fixed by real
  teaching history. Not draggable, not repacked.
- **Period / Teaching period** — one timetabled teaching slot. A chapter's
  `slot_count` is the number of teaching periods that fall inside its date
  range, computed server-side by `chapter_slot_count` (weekdays in range, minus
  effective holidays, against the CST timetable). This is the chapter's
  **capacity** and the duration auto-pack sizes against.
- **Effective holiday** — a date that is a non-teaching day for this CST after
  the org → school → CST override chain is applied. Returned by
  `GET /api/v2/csts/{cst_id}/holidays` as `effective_dates: ISODate[]` plus an
  itemised `items` list with `name`/`source`. Already fetched by the class page
  for the Timetable tab; this feature also consumes it on the Planner.

## Warning taxonomy (mirrors server `compute_range_warnings`)

Client-side, advisory, non-blocking. The teacher can save through any of them.

- **Overlap warning** — two dated chapters' ranges intersect
  (`cur.start_date <= prev.end_date` for position-consecutive dated chapters).
  The user explicitly asked for this one.
- **Holiday-in-range warning** — a chapter's date range contains one or more
  effective holidays (so its raw calendar span is longer than its teaching-day
  span). Surfaced as an inline hint, not an error.
- **Zero-teaching-days warning** *(carried for parity; optional in v1)* — a
  dated range contains no teaching periods at all (`slot_count == 0`), so a
  break-down would have nothing to size against.
