# Phase 2 — Unified timeline tab (frontend)

**Goal:** Replace the Lessons and Assessments tabs with a single **Timeline** tab that renders the merged, dated sequence from F-1.1, grouped by chapter, with a "you are here" marker, a kind filter, quiet generation status, and inline conflict/overflow warnings.

Independently shippable after Phase 1 is on staging. Frontend-only.

Files:
- `webapp/lib/dars-api.ts` — add `slots.getTimeline(cstId)` + `CstTimelineItem` types (mirror F-1.2).
- `webapp/components/templates/class-timeline-tab.tsx` — **new** template (layout only, props in; webapp layer rules in `webapp/CLAUDE.md`).
- `webapp/app/teacher-app/classes/[cst_id]/page.tsx` — fetch timeline for the new tab; derive current slot; wire mark-taught/skip + view-LP/view-exam handlers (reuse existing ones).
- `webapp/components/templates/class-detail-template.tsx` — tab list.

> Next.js here has breaking changes — read `node_modules/next/dist/docs/` before writing app code (per `webapp/AGENTS.md`).

---

## F-2.1 — API client + types

**Spec.** Add to `dars-api.ts`: `CstTimelineLessonItem`, `CstTimelineAssessmentItem`, `CstTimelineItem` (union on `kind`), `CstTimelineResponse`, and `slots.getTimeline(cstId) → CstTimelineResponse`. Mirror F-1.2 field-for-field.

**Acceptance.** Types compile; `getTimeline` hits `/api/v2/csts/{id}/timeline`.

## F-2.2 — Timeline tab replaces Lessons + Assessments (D-10)

**Spec.** In `TAB_NAMES` and `class-detail-template.tsx`, remove `"lessons"` and `"assessments"`, add `"timeline"`. Default tab stays `"today"`. Old deep links (`?tab=lessons`) should redirect/fall back to `timeline` (extend `asTab`). Delete the now-unused `class-lessons-tab.tsx` / `class-assessments-tab.tsx` only after the timeline tab covers their actions (view LP/exam, mark taught, skip, record results).

**Acceptance.** Class detail shows tabs: Today · Timeline · Timetable · Book · SLOs. `?tab=lessons` lands on Timeline without error.

## F-2.3 — Chapter-grouped, dated timeline rendering (D-2, D-6)

**Spec.** `class-timeline-tab.tsx` receives the merged items + handlers. Group by `breakdown_chapter_id` (ordered by `breakdown_chapter_position`), sticky chapter header (reuse lessons-tab styling). Within a group, render items **in position order** (lessons + assessments interleaved). Each row shows, left-to-right:
- **Projected date** (e.g. "Tue Jun 9") as the leading, primary label; muted "—" if null/overflow.
- Position `#N` (mono, secondary).
- Kind glyph: lesson rows plain; assessment rows a diamond ◆ + FA/SA tag with the rose/violet accent (keep the existing assessment color language).
- Topic: lesson `topic_title`; assessment `topic_titles.join(" · ")`.
- Status badge (planned/taught/skipped or scheduled/completed/skipped) — reuse existing badge styling.

**Acceptance.** A seeded CST shows one list per chapter with lessons and assessments interleaved by position, each with a date. Visual parity with the mock: date · #pos · kind · topic · status.

## F-2.4 — "You are here" marker (D-7)

**Spec.** The page derives the current slot using the same logic as the Today tab (today's slot from `/today`, else first `planned` lesson at/after today by position). Pass `currentSlotId` to the template; render a clear inline marker on that row (e.g. left accent bar + "Now" label) and ensure it's scrolled into view on load.

**Acceptance.** Exactly one row is marked "Now"; it matches the Today tab's notion of the current slot for the same CST.

## F-2.5 — Quiet generation status (D-8)

**Spec.** Replace the loud LP/exam pill with a small inline signal (dot + short label, muted) placed after the actions, not before the topic. `READY` → subtle "LP ready"/"Exam ready"; `not_generated` → nothing or faintest. Keep View LP / View Exam / Mark Taught / Skip / Record Results actions (reuse page handlers).

**Acceptance.** Generation state is legible but visually subordinate to date + topic; all existing actions still work from the timeline.

## F-2.6 — Kind filter (D-10)

**Spec.** A small segmented control above the list: All · Lessons · Assessments. Filters items client-side; chapter grouping + "you are here" persist within the filtered set.

**Acceptance.** Switching to Lessons hides assessment rows (and vice versa); All shows the interleaved sequence.

## F-2.7 — Conflict / overflow warnings (D-9)

**Spec.** Rows with `is_conflict` show an inline amber note ("Anchored to a non-teaching day"); `is_overflow` rows (no date) show "Beyond year-end — no date". Subtle, inline, not blocking.

**Acceptance.** A constructed conflict/overflow slot renders its warning; normal slots show none.

---

## Dependencies

- Phase 1 endpoint live on staging (F-1.1 / F-1.2).
- Reuses existing page handlers for mark-taught/skip and the LP/exam slide-over (no new backend).
