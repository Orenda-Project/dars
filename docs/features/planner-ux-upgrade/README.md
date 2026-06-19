# Planner UX Upgrade

The teacher-app chapter planner (the **Edit syllabus** mode of the Syllabus tab)
currently makes a teacher type two dates into native `<input type="date">` boxes
for every chapter and reorder chapters one at a time with ▲▼ buttons. For a
term with a dozen chapters that's two-dozen manual date entries plus a lot of
clicking — and nothing warns the teacher when two chapters end up on overlapping
dates or when a holiday eats into a chapter's teaching time.

This feature upgrades that experience to a **scheduler** pattern modelled on
mature timeline/planbook tools: the teacher sets **one anchor date** (the term
start) and the planner **auto-packs** every yet-to-start chapter back-to-back
from there, sized by each chapter's holiday-aware period count. Reorder becomes
**drag-and-drop** and re-flows all downstream dates automatically. Manual
per-chapter date override stays as an escape hatch. Two **client-side, advisory
warnings** (date overlap, holiday-in-range) surface inline, and the planner now
**shows the holidays** that fall inside the term so the teacher sees why a
chapter runs longer than its raw day-span. No schema change, no new endpoint —
the existing `setChapterDates` / `reorderChapters` mutations and the existing
`getCSTHolidays` fetch carry all of it.

## Documents (read in this order)

1. [01-decision-log.md](01-decision-log.md) — every architectural decision, indexed `D-N`. **Load-bearing — read first.**
2. [00-glossary.md](00-glossary.md) — terms used across the other docs.
3. [03-phase-1-holidays-and-warnings.md](03-phase-1-holidays-and-warnings.md) — Phase 1: show holidays on the planner + client-side overlap/holiday warnings.
4. [04-phase-2-auto-pack-and-drag.md](04-phase-2-auto-pack-and-drag.md) — Phase 2: anchor-date auto-pack + drag-to-reorder with downstream re-flow.
5. [ONRAMP.md](ONRAMP.md) — single entry point for a fresh agent picking this up cold (written after plan approval).

## Document precedence

If two docs disagree, this is the order — code is **lowest** authority. Surface
conflicts; don't silently pick a side.

```
1. 01-decision-log.md         (D-N references are canonical)
2. 00-glossary.md             (terminology)
3. phase docs                 (specs derived from above)
4. running code               (last; code may be stale)
```

There is no `02-data-model.md`: this feature adds **no** tables or columns. The
schema ground truth stays in the ancestor folder
[`docs/features/teacher-adjustable-syllabus/02-data-model.md`](../teacher-adjustable-syllabus/02-data-model.md).

## Relationship to prior features

This is a **pure frontend** evolution of the edit-mode affordances built in
[`teacher-adjustable-syllabus`](../teacher-adjustable-syllabus/) (D-13 Edit-syllabus
toggle, D-7 teacher-set dates, D-6 reorder lock). Those decisions are inherited
and **not** superseded — this feature only changes *how* the teacher produces the
same `start_date`/`end_date`/`position` values. The holiday data model and the
server-side `compute_range_warnings` taxonomy come from
[`dynamic-chapter-planner`](../dynamic-chapter-planner/) and the breakdown
calendar; we mirror the warning logic client-side rather than calling the server.
