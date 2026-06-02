# Phase 3 — Teacher Chapter Plan (break it down)

The new teacher-app flow (D-4, D-9, D-10). The teacher sees the global Syllabus Breakdown
positioned by today, and breaks a chapter into slots sized by their real timetable. May be
split into 3a (backend) + 3b (frontend) PRs if large.

**Bead:** `feat-syllabus-breakdown-phase-3-teacher-chapter-plan`
**Depends on:** Phase 2 merged.

---

## F3.1 — Resolve the Syllabus Breakdown for a class, positioned by today

**Spec.** Given a CST, resolve the published global Syllabus Breakdown for its
(curriculum, grade, subject). Return chapters with date ranges + a `current` flag on the
chapter whose range contains today (or the next upcoming if today is between/ before).
Backend endpoint e.g. `GET /csts/{cst_id}/syllabus`.

**Acceptance.** Returns ordered chapters with start/end dates and exactly one `current` marker matching today's position. 404 if no global syllabus for the combination.

## F3.2 — Slot-count = real teaching periods in range (D-9, D-14)

**Spec.** Slot count is the count of actual teaching periods in the chapter's date range —
NOT a periods×weeks approximation (D-9). It is exactly:

```
weekday_set      = { day_of_week of each timetables row for the CST }   # default {0,1,2,3,4}
holidays         = get_effective_holidays(conn, cst_id)                  # org+school+CST (D-14)
slot_count       = len(compute_teaching_days(chapter.start_date, chapter.end_date,
                                             weekday_set, holidays))
```

Reuse `projector.compute_teaching_days` verbatim and `holidays.get_effective_holidays`
verbatim — no new algorithm. This is the same calendar the timeline uses to date slots, so
generated slots map 1:1 onto real teaching dates.

**Acceptance.** A chapter Jun 1–28 with class on Mon/Wed/Fri and no holidays → count of Mon/Wed/Fri in that span. Adding a holiday on one of those dates reduces the count by 1. Unit tests cover: full weeks, partial weeks at range ends, a holiday inside the range, and an empty timetable (defaults to Mon–Fri).

## F3.3 — Generate the Chapter Plan into class slots

**Spec.** `POST /csts/{cst_id}/chapters/{book_chapter_id}/plan` (teacher-scoped). Computes
slot_count (F3.2), runs the salvaged planners (`chapter_plan_service`, D-12) to distribute
lessons/FAs/SAs/revision across slot_count and pick lp_type per topic, and inserts the
result into `class_lesson_slots` / `class_assessment_slots` (+ topics), including
`page_start`/`page_end` (kept — D-15; columns added in Phase 2's migration), at the correct
positions for that chapter. Idempotent / refuses if the chapter already has class slots
(regenerate = explicit clear first).

**Acceptance.** Calling plan on a chapter for a CST with 5 periods/week and a 4-week range creates ~20 class slots (lessons+assessments) with sensible lp_types. Re-calling without clear is a no-op/422. Generated slots appear in the existing timeline/today views.

## F3.4 — Teacher-app UI: syllabus view + break-it-down

**Spec.** In `/teacher-app/classes/[cst_id]`, add a Syllabus view: the global chapters with
date ranges, today's chapter highlighted (F3.1). Each chapter shows a **"Break it down"**
button → calls F3.3 → the chapter's slots populate the existing Timeline/Today tabs.
Teacher can then edit slots (reuse the per-slot edit affordances; this is where the salvaged
manual-edit + optional page-range UI from the old Phase 2 lands, now teacher-side).

**Acceptance.** Teacher opens a class, sees the dated syllabus with "you are here", clicks Break it down on the current chapter, and the generated lessons+assessments show in Timeline. No dashboard/admin involvement. tsc + eslint clean.

## F3.5 — Periods/timetable entry in teacher app (if not already sufficient)

**Spec.** Confirm the teacher can set periods/week (timetable day_of_week rows) for the
class in the teacher app; if the existing Timetable tab covers it, reuse. The slot-count
formula reads these rows.

**Acceptance.** Setting the class to 5 teaching days yields periods_per_week=5 in F3.2; changing it changes generated slot counts on the next break-down.

---

## Notes from execution
_(append during implementation; don't alter specs)_
