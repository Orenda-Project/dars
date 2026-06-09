# Phase 2 — Frontend: read-only syllabus tab, generate-only

Rework the teacher app's syllabus tab so the path is read-only and the only per-chapter action is "Generate chapter plan." Delete the four mutation client functions and their controls. Depends on Phase 1 (the GET now auto-seeds and drops `recommended_next`; the mutation endpoints are gone).

Bead: `feat-teacher-readonly-syllabus-phase-2-frontend`.

## F2.1 — Delete the mutation API-client functions (D-4)

**Spec:** Remove `slots.pickChapter`, `slots.setChapterDates`, `slots.reorderChapters`, `slots.removeChapter` from `webapp/lib/dars-api.ts`. Update the `SyllabusForCstResponse` / `ClassPathChapter` TS types: drop `recommended_next` (D-5). Keep `slots.getSyllabus` and `slots.breakDownChapter`.
**Acceptance:** `dars-api.ts` no longer exports the four mutations; types match the Phase 1 response. `npm run build` (or typecheck) passes.

## F2.2 — Read-only syllabus tab (D-1, D-7)

**Spec:** Rework `components/templates/class-syllabus-tab.tsx`:
- Remove all editing controls: the chapter picker / "add a chapter" dropdown, "Add next: Ch X", reorder ▲▼ buttons, remove ✕ button, and the editable date `<input type="date">` fields.
- Render each chapter row read-only: chapter number + title, position, **start/end dates shown as text** (org-decided), slot_count ("N periods"), status badge.
- Keep the per-chapter **"Generate chapter plan"** button and its disabled/reason states ("Broken down ✓" when `is_generated`; disabled with reason when slot_count is 0).
- Empty/no-breakdown state (D-7): a calm read-only message — "Your school hasn't published a syllabus for this class yet." — NOT a picker.
- Update the tab header copy to reflect that the syllabus is set by the school (org), and the teacher generates plans from it.
**Acceptance:** No control in the syllabus tab mutates the path. Dates are read-only text. The Generate button is the only action. Empty state shows the read-only message. Visually clear that the path is org-owned.

## F2.3 — Clean up the page owner + handlers (D-4)

**Spec:** In `app/teacher-app/classes/[cst_id]/page.tsx`, remove the handlers and state for the deleted mutations (`runPathMutation` and the pick/reorder/remove/date paths, `pathBusy`, `syllabusError` if only used by them — keep whatever the read + generate flow needs). Keep `handleBreakDown` / `loadSyllabus` and the Today-tab `onBreakDown` wiring. Ensure no dangling imports/props.
**Acceptance:** Page compiles with no references to deleted client functions; generate + syllabus read still work; Today tab's break-down entry still works.

## F2.4 — Verify against staging design

**Spec:** Per CLAUDE.md design rule, if colours/typography change, read `theme.pen` via pencil MCP first. This is mostly removal, so likely no token changes — but the read-only date/badge styling should match existing patterns (reuse the status badge + period count styles already in the tab).
**Acceptance:** No new design tokens introduced; read-only rows reuse existing styles.

## Notes from execution

**Shipped** on `feat/teacher-readonly-syllabus-phase-2-frontend`, stacked on PR #130 (Phase 1). Build = `next build` (Next 16 / Turbopack), which runs the TypeScript check — passed clean, all 27 routes generated. There is no standalone `tsc` in the project; build IS the typecheck.

**F2.1 (dars-api.ts):** Deleted `slots.pickChapter`, `slots.setChapterDates`, `slots.reorderChapters`, `slots.removeChapter`. Dropped `recommended_next` from `SyllabusForCstResponse` and removed the `RecommendedNextChapter` interface entirely (D-5). Kept `slots.getSyllabus` + `slots.breakDownChapter`. Refreshed the stale "teacher-adjustable" docstrings on `getSyllabus` and `ClassPathChapter` to say read-only / org-decided / auto-seeded.

**F2.2 (class-syllabus-tab.tsx):** Rewritten read-only. Props narrowed to `{ data, onBreakDown, busyChapterId }` — removed `bookChapters`, `onPick`, `onSetDates`, `onReorder`, `onRemove`, `pathBusy`. Deleted the `EmptyPathPrompt`, `AddNextRow`, `ChapterPicker`, and `ReorderButton` components; `PathRow` is now a read-only row. Each row shows: `position.` prefix, `Ch N · title`, status badge, `N periods`, and the date range as **plain text** via a `formatDate()` helper (ISO → "12 Mar 2026", "—" when null). Kept `StatusBadge` + the period-count span (existing styles, no new tokens — F2.4).

**Copy decisions:**
- Empty state (D-7): heading "Your school hasn't published a syllabus for this class yet." + sub "Once it does, the chapters will appear here and you can generate plans from them." No picker.
- Tab header: kept the `N periods/week · N chapters` line and added "Your school sets this syllabus. Generate a plan from any chapter below."
- Generate-button disabled reason: where the editable version said "Set dates first", the read-only version can't set dates, so the `slot_count === 0` state now reads **"No periods to plan"** (title: "This chapter has no teaching periods in its date range yet"). "Broken down ✓" unchanged for `is_generated`.

**F2.3 (page.tsx):** Removed `runPathMutation`, `handlePick`, `handleSetDates`, `handleReorder`, `handleRemove`, the `pathBusy` state, the `syllabusBookChapters` state + `loadSyllabusBookChapters` loader, and their entries in the tab-load effect body + dep array. Kept `handleBreakDown`, `loadSyllabus`, `syllabusError`, `busyChapterId`, and the Today-tab `onBreakDown` wiring (unchanged). `BookChapter` type + `booksApi` import retained — still used by the Book tab's `loadBook`.

**Deviations:** none beyond the "No periods to plan" copy above (a necessary substitute for the removed "Set dates first", since dates are no longer teacher-editable). No design-token or color/typography change, so `theme.pen` was not consulted (per F2.4).
