# Phase 1 — Exam Periods & Breakdown Holidays

**Goal:** an admin can reserve exam date ranges *and* general holiday ranges (Eid, etc.) on a global Syllabus Breakdown; both are excluded from teaching-day derivation in the admin display and inherited into the teacher's class plan. Independently shippable to staging.

Decisions in play: D-1, D-2, D-3, D-4, D-5, D-14, D-15. Schema in `02-data-model.md`.

---

## F-1.1 — Schema: `exam_periods` + `breakdown_holidays`

**Spec:** New migration `server/src/dars/migrations/20260610000000_exam_periods_and_breakdown_holidays.sql` creating both tables + indexes exactly as in `02-data-model.md`. Append-only.

**Acceptance:**
- Migration applies cleanly on a fresh DB and on the current staging schema (additive only).
- Both tables exist with FK → `syllabus_breakdowns` ON DELETE CASCADE and their indexes.
- No edits to any prior migration.

**Dependencies:** none.

---

## F-1.2 — Calendar exclusion: expand ranges and union into holidays

**Spec:** In `breakdown/chapter_calendar.py` (or alongside the calendar helpers), add `expand_ranges(rows) -> set[date]` that walks each `[start_date, end_date]` inclusive and returns the union of all dates. Add async helpers `get_breakdown_exam_dates(conn, syllabus_breakdown_id) -> set[date]` and `get_breakdown_holiday_dates(conn, syllabus_breakdown_id) -> set[date]` reading the two new tables and expanding. (D-2, D-14.)

**Acceptance:**
- `expand_ranges` is pure, unit-tested (single-day range → 1 date; multi-day → inclusive span; empty → empty set).
- The two getters return the correct date set for a breakdown and an empty set for a breakdown with none / a `None` id.

**Dependencies:** F-1.1.

---

## F-1.3 — Admin derivation excludes exam + holiday dates

**Spec:** Where the admin breakdown computes `derived_teaching_days` per chapter (the `router_syllabus` GET/detail path via `chapter_calendar.derived_teaching_days` / `compute_range_warnings`), pass `holidays = get_breakdown_exam_dates(...) ∪ get_breakdown_holiday_dates(...)` for that breakdown instead of the empty set. (D-2.) The advisory `compute_range_warnings` now naturally flags a chapter whose range has zero teaching days because it's fully inside an exam/holiday window (D-4).

**Acceptance:**
- A breakdown with an exam period over part of a chapter's range shows a *reduced* `derived_teaching_days` for that chapter.
- A chapter range fully inside an exam/holiday window surfaces a `zero_teaching_days` warning.
- A breakdown with no exam periods / holidays behaves exactly as before (regression).

**Dependencies:** F-1.2.

---

## F-1.4 — Teacher projection inherits breakdown exam + holiday dates

**Spec:** In `breakdown/chapter_plan_service.py` (`chapter_slot_count`) and `breakdown/projector.py` (`project_cst_schedule`), union the resolved breakdown's exam + holiday dates into the holiday set. The breakdown id is already resolved by `resolve_cst_syllabus_context` (`CstSyllabusContext.syllabus_breakdown_id`); thread it through so `chapter_slot_count` / projection compute `get_effective_holidays(cst_id) ∪ get_breakdown_exam_dates(id) ∪ get_breakdown_holiday_dates(id)`. If `syllabus_breakdown_id is None`, the extra sets are empty (graceful, D-3). (D-2, D-3, D-15.)

**Acceptance:**
- For a CST whose published breakdown has an exam period, the chapter's `slot_count` (break-it-down) is reduced by the exam teaching days that fall in the chapter's class-path range.
- The projector never assigns a lesson/assessment slot a `projected_date` inside an exam or breakdown-holiday window.
- A CST with no published breakdown is unaffected (regression).
- Org/school/CST holidays still apply (the union is additive — prior D-26 intact, D-15).

**Dependencies:** F-1.2.

---

## F-1.5 — CRUD endpoints for exam periods + breakdown holidays

**Spec:** In `router_syllabus.py`, add nested endpoints under a breakdown:

```
POST   /api/v2/syllabus-breakdowns/{id}/exam-periods         {start_date, end_date, name}
PATCH  /api/v2/syllabus-breakdowns/{id}/exam-periods/{ep_id} {start_date?, end_date?, name?}
DELETE /api/v2/syllabus-breakdowns/{id}/exam-periods/{ep_id}
POST   /api/v2/syllabus-breakdowns/{id}/holidays             {start_date, end_date, name}
PATCH  /api/v2/syllabus-breakdowns/{id}/holidays/{h_id}      {start_date?, end_date?, name?}
DELETE /api/v2/syllabus-breakdowns/{id}/holidays/{h_id}
```

The breakdown detail (`GET /syllabus-breakdowns/{id}`) response gains `exam_periods: [...]` and `holidays: [...]` arrays. All mutations are rejected (409) if the parent breakdown is `published` (D-5), reusing the existing publish-lock guard. Structured logging on every endpoint (project rule 11).

**Acceptance:**
- Create/list/update/delete round-trips for both kinds, scoped to the breakdown.
- Mutation on a published breakdown → 409.
- Breakdown detail returns both arrays; deleting the breakdown cascades.
- `end_date < start_date` is rejected (422) with a clear message.

**Dependencies:** F-1.1.

---

## F-1.6 — Admin UI: exam periods + holidays sections

**Spec:** In `webapp/app/dashboard/syllabus-breakdowns/[breakdown_id]/page.tsx`, add two clearly-labelled sections (above or beside the chapter list): **Exam Periods** and **Holidays**, each a list of named date ranges with add / edit / delete (date pickers + name). Disabled (read-only) when the breakdown is published (D-5). The per-chapter `derived_teaching_days` display already reflects exclusions from F-1.3, so adding an exam period visibly reduces the affected chapters' teaching-day counts and may raise a zero-teaching-days warning. Follow `docs/design-system.md`; read `theme.pen` before touching colours/type (project rule 9).

**Acceptance:**
- Admin can add "1–20 August — Mid-term exams" and "Eid-ul-Fitr" ranges and see them listed.
- Editing a chapter's dates into an exam window shows the warning; teaching-day counts update.
- Published breakdown: sections render read-only.

**Dependencies:** F-1.5, F-1.3.

---

## Phase 1 ship criteria

All F-1.x acceptance met; both Railway services green on the merge; admin can reserve exam + holiday ranges and they flow into both the admin display and a teacher's break-it-down slot count.
