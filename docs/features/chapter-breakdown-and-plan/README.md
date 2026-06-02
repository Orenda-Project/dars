# Chapter Breakdown & Chapter Plan

Splits breakdown authoring into **two explicit, separately-editable actions on the dashboard**, where today the auto-build algorithm does both implicitly.

1. **Chapter Breakdown** — deciding *which chapter is taught when*: ordering chapters and assigning each an explicit calendar **date range** (e.g. "Chapter 1: Jun 10 – Jun 25, then Chapter 3, then Chapter 2"). Editable directly from the dashboard, calendar-aware.
2. **Chapter Plan** — taking one chapter and **manually** breaking it into a sequence of typed slots (lesson plans + formative assessments), each with a **page range** and type (e.g. "LP1: pages 1–10, reading; Day 2: formative assessment, pages 1–10"). Manual-first; auto-build demoted to an optional "seed a starting point" action.

The **global-scope breakdown remains the reference / default** a teacher compares against (existing fork mechanism, D-7); no change to scoping. All authoring stays on `/dashboard/breakdowns/...` — the teacher-app only consumes the result.

---

## Documents

1. [`00-glossary.md`](00-glossary.md) — terms specific to this feature.
2. [`01-decision-log.md`](01-decision-log.md) — frozen design decisions (D-1…).
3. [`02-data-model.md`](02-data-model.md) — schema deltas (two new sets of columns).
4. [`03-phase-1-chapter-breakdown-dates.md`](03-phase-1-chapter-breakdown-dates.md) — Phase 1: explicit per-chapter date ranges.
5. [`04-phase-2-chapter-plan-manual.md`](04-phase-2-chapter-plan-manual.md) — Phase 2: manual Chapter Plan builder + page ranges.
6. [`ONRAMP.md`](ONRAMP.md) — single entry point for any agent picking this up (written after plan approval).

## Document precedence

```
1. 01-decision-log.md   (D-N references are canonical)
2. 02-data-model.md     (schema is ground truth)
3. 00-glossary.md       (terminology)
4. phase docs           (specs derived from above)
5. running code         (last; code may be stale)
```

If two docs disagree, this is the order. Code is lowest authority. Surface conflicts; don't silently pick a side.

## Inherited context

This feature builds directly on the v2 rebuild and the shipped `breakdown-slot-editing` feature. It inherits their glossary and the breakdown data model at `docs/plans/2026-05-15-dars-v2-rebuild/02-data-model.md` (Section 4: breakdowns / breakdown_chapters / breakdown_slots / breakdown_slot_topics).
