# Phase 1 — Holidays on the planner + client-side warnings

**Goal:** the teacher sees the holidays that fall inside their term right on the
planner, and gets inline advisory warnings when two chapters overlap or a
chapter's range straddles a holiday. No date-entry mechanics change yet — this
phase is additive and independently shippable.

**Why first:** these are the two concrete deliverables the user named, they
touch the smallest surface (read-only holiday rendering + a pure client
function), and they de-risk Phase 2 — the same holiday set and overlap logic
feed auto-pack.

**Independently shippable to staging:** yes. After this phase the planner still
uses the existing date inputs + ▲▼, but now shows holidays and warns on overlap.

---

## F1.1 — Lift effective-holiday data into the Syllabus tab

**Spec.** The class page (`webapp/app/teacher-app/classes/[cst_id]/page.tsx`)
already fetches effective holidays for the Timetable tab via
`holidaysApi.getCSTHolidays(cstId)` → `{ items: Holiday[]; effective_dates: ISODate[] }`,
stored in `holidaysData` and currently loaded only when `activeTab === "timetable"`.

- Also trigger `loadHolidays()` when `activeTab === "syllabus"` (and
  `holidaysData === null`). It's a cheap, cached, idempotent fetch.
- Pass the holiday data into `ClassSyllabusTab` as new props:
  `effectiveHolidays: Set<string>` (built once from `effective_dates`) and
  `holidayItems: Holiday[]` (for names/sources in the legend/tooltips).
- Keep the template prop-driven (webapp layering): the page owns the fetch and
  the `Set` memoisation; the template only renders.

**Acceptance.**
- Opening the Syllabus tab fetches holidays once; switching to Timetable and
  back does not refetch.
- `ClassSyllabusTab` receives a non-null holiday set whenever holidays exist for
  the CST; an empty set when there are none (never crashes on null).

**Dependencies:** none.

---

## F1.2 — Render holidays inline on each dated chapter row

**Spec.** In `class-syllabus-tab.tsx`, for each path row that has a full date
range, compute the effective holidays that fall inside `[start_date, end_date]`
and surface them:

- A small inline hint under the date range, both VIEW and EDIT mode:
  e.g. `🏖 2 holidays in range` (count). On hover/focus, a tooltip lists the
  holiday names + dates (from `holidayItems`).
- The hint explains the gap between calendar span and teaching span — pair it
  with the existing `{slot_count} periods` label so the teacher reads
  "12 Mar → 28 Apr · 14 periods · 🏖 2 holidays".
- Use Dars tokens (`text-dars-muted`, `text-dars-terra` for emphasis); no new
  color. Match the existing row typography.

**Acceptance.**
- A chapter whose range contains an effective holiday shows the count hint with
  the correct number; a chapter with no holidays in range shows no hint.
- The tooltip lists each in-range holiday's name (falls back to the date when
  `name` is null) and date.
- Holiday hint renders in both VIEW and EDIT mode.

**Dependencies:** F1.1.

---

## F1.3 — Client-side overlap + zero-teaching-day warnings

**Spec.** Port the server's `compute_range_warnings` overlap/zero-teaching logic
(`server/src/dars/breakdown/chapter_calendar.py`) to a pure TypeScript helper in
`webapp/lib/` (e.g. `planner-warnings.ts`):

```
computePlannerWarnings(chapters, effectiveHolidays) -> Warning[]
```

where each `Warning` is `{ type: "overlap" | "zero_teaching_days"; chapterIds: string[] }`.
Mirror the server rules exactly:
- Consider only chapters with BOTH dates set; sort by `(start_date, position)`.
- **overlap**: for each position-consecutive pair, `cur.start_date <= prev.end_date`.
- **zero_teaching_days**: a dated range with no teaching day (weekday-in-range
  minus holiday) — equivalently `slot_count === 0` on a dated row, which the
  payload already gives us; prefer reading `slot_count` over recomputing.
- (Holiday-in-range is handled visually by F1.2, not as a `Warning` row.)

Surface in the tab:
- An advisory banner at the top of the path when any warning exists
  (e.g. "⚠ Some chapters overlap — adjust the dates or reorder."). Non-blocking;
  uses a soft warning treatment in Dars tokens, never red-error styling.
- A subtle per-row marker on each chapter named in a warning (ring/badge) so the
  teacher can find the offending rows.

**Acceptance.**
- Two chapters dated to overlapping ranges produce exactly one overlap warning
  naming both; fixing the dates clears it live (warnings recompute from props on
  every render, no stale state).
- A chapter dated to a range with zero teaching periods produces a
  zero-teaching warning.
- Warnings never block a `setChapterDates` save — the existing onBlur persist
  still fires; the banner just appears/updates.
- The TS helper's overlap output matches the Python `compute_range_warnings`
  overlap output for the same inputs (spot-checked with a unit test in
  `webapp` if a test harness exists; otherwise a documented manual check).

**Dependencies:** F1.1 (holiday set for zero-teaching parity).

---

## Notes from execution

_(Append findings, scope changes, and follow-ups here during the build. Do not
rewrite the specs above.)_
