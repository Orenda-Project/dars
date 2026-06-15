# Phase 3 — Revival: restore teacher edits on the auto-seeded class path

The class path was shipped (#109), then frozen read-only (`teacher-readonly-syllabus`,
#130/#131). This phase **re-opens** teacher editing — full pick / set-dates / reorder /
remove — on top of today's auto-seeded, expandable syllabus tab. See D-9…D-12.

**Bead:** `feat-teacher-adjustable-syllabus-phase-3-revival`
**Depends on:** nothing new (the `class_chapters` table, auto-seed, and `list_class_path`
already live on staging). No migration — the schema (`02-data-model.md`) is unchanged.

**Ships as ONE PR → staging** (backend + frontend together; small, tightly coupled).

**Baseline to lift from:** commit `91e1763` (PR #109). The backend functions/endpoints/
schemas it added can be restored near-verbatim; the frontend must be grafted onto the
current expandable tab, not reverted (D-12).

> **⚠️ Collision with `lp-context-header` (in flight).** That feature's Phase 3
> (`docs/features/lp-context-header/05-phase-3-syllabus-chapter-page.md`, F-3.3) **removes
> the inline accordion + `<ChapterContents>` from `class-syllabus-tab.tsx`** and turns each
> chapter row into a `Link` to a new page `/teacher-app/classes/[cst_id]/chapters/[position]`.
> This revival's F3.4 grafts edit controls onto that same `PathRow`. They rewrite the same
> file in incompatible directions. **Before executing F3.4/F3.5, check whether
> `lp-context-header` Phase 3 has merged** (route exists at
> `webapp/app/teacher-app/classes/[cst_id]/chapters/[position]/page.tsx`). Sequencing is a
> user decision (see D-15). If it merged first, the edit affordances + Edit-mode toggle go on
> the **Chapter Page** (and/or a tab-level edit mode over the now-navigation row list), NOT
> the removed accordion. The backend (F3.1–F3.3) and api client are unaffected either way.

---

## F3.1 — Restore path mutation service functions

**Spec.** Re-add to `server/src/dars/breakdown/class_chapter_service.py` (lift from
`91e1763`, keep the structured-logging convention — entry/exit INFO, errors ERROR
exc_info):
- `pick_chapter(conn, cst_id, org_id, book_chapter_id)` → insert at `max(position)+1`
  (or 1). 422 if the chapter is already in the path or doesn't belong to the CST's book.
  Undated (D-7).
- `set_chapter_dates(conn, cst_id, book_chapter_id, start, end)` → patch the row's dates.
  **Use `COALESCE`** so sending one bound doesn't wipe the other. 422 if the chapter isn't
  in the path.
- `reorder_path(conn, cst_id, ordered_book_chapter_ids)` → rewrite positions 1..N in one
  transaction (bump to avoid the `(cst_id, position)` unique collision). Validates via
  `validate_reorder` (D-6 lock).
- `validate_reorder(current_order, current_statuses, submitted_order)` → pure logic:
  submitted set must equal current set; started (status≠yet_to_start) chapters stay at the
  front in their current relative order. Raises `ValueError` (→ 422) otherwise.
- `remove_chapter(conn, cst_id, book_chapter_id)` → delete the path row. **D-11 change vs
  #109:** raise `ValueError` (→ 422) if the chapter has ANY row in
  `class_lesson_slots`/`class_assessment_slots` for `(cst_id, book_chapter_id)` — not just
  if it has *terminal* slots. Message: "this chapter has a generated plan; clear it before
  removing." (Still also rejects status≠yet_to_start, D-6.)
- `recommended_next_chapter(conn, cst_id)` → already restorable; lowest-position published-
  breakdown chapter not in the class path; empty path → the breakdown's first; None if the
  path covers everything or there's no published breakdown (D-3).

**Keep `list_class_path` and `seed_class_chapters_from_breakdown` exactly as they are on
staging** (D-10 — auto-seed stays).

**Acceptance.** Pick / set-dates / reorder / remove unit-tested with the same shape as
#109's 19 logic tests (restore `validate_reorder` tests verbatim; add one for D-11:
removing a chapter with a non-terminal slot 422s). Non-DB suite green.

## F3.2 — Restore the mutation endpoints

**Spec.** Re-add to `server/src/dars/v2_api/router_class_actions.py` (lift from `91e1763`,
tenancy enforced via the existing `_ensure_cst_in_org` / `get_current_org`; all return the
full updated `SyllabusForCstResponse` so the client re-renders from one payload):
- `POST   /csts/{cst_id}/chapters`                      `{ book_chapter_id }` → pick (201)
- `PATCH  /csts/{cst_id}/chapters/{book_chapter_id}`    `{ start_date?, end_date? }` → set dates
- `PUT    /csts/{cst_id}/chapters/order`                `{ book_chapter_ids: [...] }` → reorder
- `DELETE /csts/{cst_id}/chapters/{book_chapter_id}`    → remove

Restore the request schemas in `schemas_class_actions.py`: `PickChapterBody`,
`SetChapterDatesBody`, `ReorderChaptersBody`. The response models (`ClassPathChapter`
incl. `is_generated`/`status`, `SyllabusForCstResponse`, `RecommendedNextChapter`) already
exist on staging — reuse, don't duplicate.

**Note:** `GET /csts/{cst_id}/syllabus` is **not** reworked — it already returns the path +
recommendation + auto-seeds. Leave it.

**Acceptance.** Full pick→date→reorder→remove cycle works via the API against a seeded CST.
A CST outside the caller's org 404s on every mutation. `ValueError`s surface as 422 with
the message. Removing a broken-down chapter 422s (D-11).

## F3.3 — Restore the webapp API client functions

**Spec.** Re-add to the `csts` namespace in `webapp/lib/dars-api.ts` (the names #109 used):
`pickChapter`, `setChapterDates`, `reorderChapters`, `removeChapter` — each calling the
F3.2 endpoint and typed to return `SyllabusForCstResponse`. `getSyllabus` /
`breakDownChapter` already exist; don't touch them.

**Acceptance.** `tsc` clean; functions callable with the documented signatures.

## F3.4 — Add an explicit "Edit syllabus" mode to the expandable tab (D-13)

**Spec.** Edit the CURRENT `webapp/components/templates/class-syllabus-tab.tsx` — do not
revert it. Keep the expandable `PathRow` + `ChapterContents` exactly, and keep them working
in BOTH modes (expand → view LP, mark-taught, generate, break-it-down). The cloned class
breakdown shows as-set by default; an **Edit syllabus** toggle reveals the editing controls.

**View mode (default):** today's read view — chapter rows with date range as **plain text**,
status badge, slot count, expand-to-contents, and the per-chapter "Break it down" button.
A single **Edit syllabus** button at the top of the tab.

**Edit mode (after the toggle):** the same rows, now with the D-12 controls; a **Done**
button (and the top button becomes "Done") exits back to view mode:
- **Date editing:** the plain-text date range becomes two `<input type="date">`
  (start/end), pre-filled from `ch.start_date`/`ch.end_date`; on `blur`, if changed, call
  `onSetDates(book_chapter_id, { start_date | end_date })`. Stop click propagation so
  editing a date doesn't toggle the row.
- **Reorder ▲▼:** small up/down buttons in the header; disabled (not rendered as handles)
  when `ch.status !== "yet_to_start"` (D-6). On click, compute the reordered
  `book_chapter_id[]` and call `onReorder`.
- **Remove ✕:** disabled unless `status === "yet_to_start"` AND `!ch.is_generated` (D-11).
  Calls `onRemove(book_chapter_id)`.
- **Add a chapter:** below the path, an "add a chapter" affordance — highlight
  `data.recommended_next` if present ("Suggested next: Ch N — <title>") plus a picker of any
  book chapter not already in the path. Calls `onPick(book_chapter_id)`. (Needs the book's
  chapter list as a prop — restore `bookChapters` from #109's page wiring.)

**Empty path:** keep the calm `EmptyPathMessage` only when there's no recommendation; when
the path is empty but a recommendation exists (no auto-seed because no published breakdown),
show the #109 recommendation prompt so the teacher can start the path (this implies edit
mode for an empty path).

Per webapp/CLAUDE.md: `templates/` is layout-only — all data + callbacks come in as props;
no hooks/fetching in the template. New props: `editing: boolean`, `onToggleEdit: () => void`,
`onPick`, `onSetDates`, `onReorder`, `onRemove`, `bookChapters`, `pathBusy`. Update the
comment header (it still says "READ-ONLY path").

**Acceptance.** Default view shows the cloned breakdown as plain text with an "Edit
syllabus" button and no editing controls. Clicking it reveals date inputs / reorder /
remove / add; "Done" hides them again. In edit mode a teacher can re-date a chapter
(persists, `slot_count` recomputes), reorder upcoming chapters (locked ones show no handle),
remove a yet-to-start un-generated chapter, and add a chapter. Break-it-down and
expand-to-contents work in BOTH modes — no regression.

## F3.5 — Re-wire the page handlers + edit-mode state (D-12, D-13)

**Spec.** In `webapp/app/teacher-app/classes/[cst_id]/page.tsx`, restore from #109:
`runPathMutation(mutate)` (sets busy, calls, `setSyllabus(res)` from the returned payload,
surfaces errors), and `handlePick / handleSetDates / handleReorder / handleRemove` bound to
the F3.3 client functions. Own the **`editing` boolean state** here (D-13 — template stays
prop-driven) and pass `editing` + `onToggleEdit`. Fetch the book's chapter list for the
picker (the book is resolvable from the syllabus response's curriculum/grade/subject context
— reuse whatever #109 used, or the existing books API). Pass the new props to
`<ClassSyllabusTab>`.

**Acceptance.** The Edit/Done toggle flips the tab between view and edit modes. Each
mutation updates the tab from its response without a full reload; errors show inline; the
Today tab still reflects path order/dates.

---

## Notes from execution
_(append during implementation; don't alter specs)_

**2026-06-15 — built on `feat/teacher-adjustable-syllabus-revival` (off `origin/staging`). One branch, commit left for the parent to PR; NOT pushed.**

What shipped, by feature:

- **F3.1 (service).** Merged the removed functions back into today's
  `class_chapter_service.py` (kept staging's `list_class_path` w/ `is_generated` +
  `seed_class_chapters_from_breakdown` verbatim, D-10): `validate_reorder` (verbatim from
  #109), `pick_chapter`, `set_chapter_dates` (uses **COALESCE** so one bound doesn't wipe the
  other, per spec), `reorder_path`, `recommended_next_chapter`, and `remove_chapter` with the
  **D-11** change — it rejects a chapter that has ANY row in `class_lesson_slots` /
  `class_assessment_slots` (via the existing `_chapter_terminal_map`, whose per-chapter list
  is non-empty as soon as the chapter is broken down, terminal or not), message "this chapter
  has a generated plan; clear it before removing."; the D-6 status-lock is kept as a
  belt-and-braces second check.
- **F3.2 (endpoints + schemas).** Added `POST /csts/{id}/chapters`,
  `PATCH /csts/{id}/chapters/{book_chapter_id}`, `PUT /csts/{id}/chapters/order`,
  `DELETE /csts/{id}/chapters/{book_chapter_id}` to `router_class_actions.py` — tenancy via
  the existing `_ensure_cst_in_org` (404 cross-org), `ValueError → 422`, each echoes the full
  updated `SyllabusForCstResponse`. Restored `PickChapterBody` / `SetChapterDatesBody` /
  `ReorderChaptersBody`. **Deviation (D-16):** had to re-add `RecommendedNextChapter` + the
  `recommended_next` field on `SyllabusForCstResponse` (additive/defaulted) — the read-only
  reversal had stripped them too, contrary to the spec's "already exists" note. The GET was
  otherwise left as-is (auto-seed call intact).
- **F3.3 (api client).** Added `pickChapter` / `setChapterDates` / `reorderChapters` /
  `removeChapter` to the `csts` namespace in `dars-api.ts`, plus the `RecommendedNextChapter`
  TS interface + `recommended_next` on `SyllabusForCstResponse`.
- **F3.4 (UI, D-13).** Grafted onto the accordion (**D-17** — no Chapter Page on staging at
  build time). `class-syllabus-tab.tsx` now takes `editing`/`onToggleEdit`/`onPick`/
  `onSetDates`/`onReorder`/`onRemove`/`bookChapters`/`pathBusy`. View mode = plain-text dates,
  no controls, "Edit syllabus" button. Edit mode reveals per-chapter `<input type="date">`
  (onBlur → `onSetDates`, click-stop so it doesn't toggle the row), reorder ▲▼ (rendered only
  for `yet_to_start`, locked rows show 🔒), remove ✕ (only `yet_to_start && !is_generated`,
  else "Can't remove" + reason), and a tab-level `AddChapterPanel` (highlights
  `recommended_next` + a `<select>` of book chapters not in the path). Restructured `PathRow`
  so the toggle is the title region only (no nested interactive controls). Expand-to-contents
  / break-it-down work in BOTH modes. Empty-path-with-recommendation shows the add panel.
- **F3.5 (page).** `[cst_id]/page.tsx` owns `editingSyllabus` + `pathBusy` + `pickerChapters`;
  `runPathMutation` sets busy, calls, `setSyllabus(res)` from the payload, refreshes
  timeline/today when loaded, and re-`loadSyllabus()` on error (so a rejected reorder/remove
  re-syncs the inputs). `handlePick/handleSetDates/handleReorder/handleRemove` bound to the
  F3.3 client; the picker list is lazy-fetched (lightweight `booksApi.getBookChapters`) the
  first time edit mode opens.

**Tests.** `test_class_chapter_service.py`: restored the 11 `validate_reorder` tests verbatim
(→ 19 pure-logic tests total with the 8 status tests) + 2 DB-gated `remove_chapter` tests (the
D-11 reject-when-a-non-terminal-slot-exists + a no-slots control). Full backend suite:
**311 passed, 62 skipped** (DB-gated skipped — no `DATABASE_URL`). Frontend (after `npm ci`):
`npx tsc --noEmit` exit **0**; `eslint` on the 3 changed files exit **0** (2 pre-existing
`_id` warnings in `dars-api.ts`, unrelated); `npm run build` exit **0** (all routes,
`/teacher-app/classes/[cst_id]` compiled). No migration this phase (rule 7 honoured).

**Deferred / not done.** None of the F3.x scope. The recommendation prompt for a genuinely
empty path is covered by the same `AddChapterPanel` (shown when empty + a recommendation
exists). Optional polish left for later: drag-reorder instead of ▲▼; a confirm on remove.
