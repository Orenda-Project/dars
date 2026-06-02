# Phase 1 — Chapter Breakdown: explicit date ranges

Make chapter timing an explicit, directly-editable calendar date range on the dashboard. Order is implied by dates. One PR, targets `staging`.

**Bead:** `feat-chapter-breakdown-and-plan-phase-1-dates`
**Depends on:** nothing (additive schema; builds on shipped `breakdown-slot-editing`).

---

## F1.1 — Schema delta: chapter date range

**Spec.** Add `start_date` / `end_date` (DATE NULL) to `breakdown_chapters` per Delta 1 in `02-data-model.md`. Migration `20260602000000_breakdown_chapters_date_range.sql`. Update ORM model + `BreakdownChapterRead`/`Create`/`Update` schemas to expose and accept both.

**Acceptance.** Migration file present in `server/src/dars/migrations/`. `GET` a breakdown returns `start_date`/`end_date` (null for existing rows). `PATCH` a chapter accepts them. SQLite test suite green.

## F1.2 — Derived teaching days from calendar

**Spec.** Given a chapter's `start_date`/`end_date`, compute the count of actual teaching days in that span using the academic calendar (weekends + holidays excluded). Reuse the existing calendar logic — locate via `graphify query "where is teaching days computed from academic calendar"`; do not reimplement. Expose the derived count on `BreakdownChapterRead` (e.g. `derived_teaching_days`) alongside the stored `teaching_days` (D-2).

**Acceptance.** A chapter with a date range returns a `derived_teaching_days` matching a hand-checked count for the seed calendar. A chapter with no range returns null derived and falls back to stored `teaching_days`.

## F1.3 — Advisory validation

**Spec.** Per D-5, compute (server-side, returned in the chapter/breakdown read or a dedicated validate endpoint) advisory warnings: chapter ranges that **overlap**, **gaps** between consecutive chapters, and ranges with **zero teaching days**. Non-blocking — saves always succeed.

**Acceptance.** Two chapters with overlapping ranges produce an `overlap` warning; a gap produces a `gap` warning; a range entirely on weekends/holidays produces a `zero_teaching_days` warning. Saving still returns 200.

## F1.4 — Dashboard editor: per-chapter date ranges

**Spec.** In `webapp/app/dashboard/breakdowns/[breakdown_id]/page.tsx` (the existing breakdown editor — extend, don't replace), make each chapter's date range directly editable: two date pickers (start/end) per chapter row. Display the derived teaching-day count. Order chapters by `start_date`. Surface F1.3 warnings inline (badge/tooltip), non-blocking. Wire to the chapter PATCH endpoint.

**Acceptance.** Editing a chapter's dates on the dashboard persists and re-renders the ordered list with updated derived days. Overlap/gap warnings show inline. No teacher-app changes (D-6).

---

## Notes from execution

**2026-06-02 — all features implemented (PR open to staging).**
- F1.1: migration `20260602000000_breakdown_chapters_date_range.sql`; schemas updated. Note: breakdowns use raw asyncpg SQL, no SQLAlchemy ORM model — only the SQL + Pydantic schemas changed.
- F1.2: `chapter_calendar.derived_teaching_days` reuses `projector.compute_teaching_days` verbatim. Calendar source resolved best-effort by scope (D-8), since breakdowns have no CST.
- F1.3: `chapter_calendar.compute_range_warnings` → `BreakdownRead.chapter_range_warnings`. Non-blocking (D-5).
- F1.4: date pickers **replaced** the day-count `<input>` (D-2 makes dates primary); derived days shown in the chapter subtitle; warning badges inline; chapters sorted by `start_date`. New decision D-8 logged (Mon–Fri minus org holidays; None=omit on PATCH).
- Tests: 7 in `tests/test_chapter_calendar.py`; full non-DB suite 152 passed. Webapp tsc + eslint clean.
