# Decision Log

**D-1: Add a new "Today" tab and make it the default instead of Lessons.**
*Rationale:* The user wants "what to do in today's class" to be the landing view
for a class, not the lessons list. Keeping it as a tab (rather than a separate
route) preserves the existing tab shell, breadcrumbs, and header, and lets the
old Lessons view stay one click away. *Apply:* `class-detail-template.tsx` adds
`today` as the first tab; `page.tsx` `asTab()` default returns `"today"`.
*Decided:* 2026-06-01.

**D-2: Frontend-only — reuse existing endpoints, no new backend.**
*Rationale:* Everything the dashboard needs is already exposed: `/api/v2/today`
(today's slot per CST), the per-CST lesson-slots list (covered/now/next), and
sub-SLO coverage (progress %). A dedicated overview endpoint would be cleaner
but adds a backend phase for no new capability. Ships in one PR.
*Apply:* new `loadToday()` in `page.tsx` calls `todayApi.get()` and filters by
`cst_id`; reuses `loadLessons()` data and `progressApi.getSubSLOCoverage()`.
*Decided:* 2026-06-01.

**D-3: "Now" falls back to the next planned slot when nothing is scheduled
today.** *Rationale:* On holidays / non-class days `/api/v2/today` returns no
entry for the CST. The dashboard should still orient the teacher ("you're up to
Day 7; next is Day 8"), so Now = today's slot if present, else the
lowest-position `planned` lesson slot. *Apply:* derive in `page.tsx` from the
lessons list. *Decided:* 2026-06-01.

**D-4: Mark-taught and View-LP/exam are available directly from the dashboard.**
*Rationale:* The whole point is a teacher can act on today's class without
navigating away. Reuse the existing `slotsApi.markTaught` + `SlideOver`/
`LPViewer` already wired in the class detail page. *Decided:* 2026-06-01.
