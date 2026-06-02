# Syllabus Breakdown & Teacher Chapter Plan

A ground-up re-architecture of the breakdown system. It splits one over-loaded
admin artifact into two cleanly-owned pieces and moves slot generation to where
it belongs — the teacher.

**Before:** a single admin/global breakdown held *both* chapter date-ranges *and*
the full slot sequence (lessons + assessments). Org admins forked global→org→class,
and class breakdowns were "realized" into per-class slots. Slot authoring lived on
the dashboard.

**After:**
1. **Syllabus Breakdown** — the *only* admin/global artifact. Dars-owned, global-scope
   only. Pure chapter→date-range: "Teach Chapter 1 from x to y, then Chapter 2, …".
   No slots. (This is the renamed, slimmed "Chapter Breakdown".)
2. **Chapter Plan** — now a **teacher-only** feature in the teacher app. The teacher
   creates classes + assigns periods/week (timetable), sees the global Syllabus
   Breakdown positioned by today's date ("you should be on Chapter 2"), and hits
   **"break it down"** on a chapter. Slot count is **computed**:
   `periods/week × weeks-in-chapter-range` → that many lesson + assessment slots,
   generated into the class's own slot tables and editable by the teacher.

Org/class breakdown scope, forking, admin slot authoring, auto-build, and
realization are **removed**. The DB tables are renamed to `syllabus_breakdowns` /
`syllabus_chapters` for end-to-end consistent naming (D-7). The data bank
(curriculums, grades, subjects, SLOs, sub-SLOs, books, chapters, topics) is **untouched**.

This is also a **cleanup** pass: dead code from the old model is deleted, not
left dangling (per the "build from the ground up" mandate, 2026-06-02).

---

## Documents

1. [`00-glossary.md`](00-glossary.md) — terms (Syllabus Breakdown, Chapter Plan, periods, slot-count formula).
2. [`01-decision-log.md`](01-decision-log.md) — frozen decisions D-1….
3. [`02-data-model.md`](02-data-model.md) — final schema: what's dropped, kept, repurposed.
4. [`03-phase-1-rename-syllabus.md`](03-phase-1-rename-syllabus.md) — rename Chapter Breakdown → Syllabus Breakdown everywhere.
5. [`04-phase-2-demolition.md`](04-phase-2-demolition.md) — remove slots/fork/auto-build/realize at admin scope; drop dead code + tables.
6. [`05-phase-3-teacher-chapter-plan.md`](05-phase-3-teacher-chapter-plan.md) — teacher-app break-it-down flow + slot-count formula + generation.
7. [`ONRAMP.md`](ONRAMP.md) — single entry point for any agent picking this up.

## Document precedence

```
1. 01-decision-log.md   (D-N references are canonical)
2. 02-data-model.md     (schema is ground truth)
3. 00-glossary.md       (terminology)
4. phase docs           (specs derived from above)
5. running code         (last; code may be stale)
```

If two docs disagree, this is the order. Surface conflicts; don't silently pick a side.

## Supersedes

This re-architects the shipped `chapter-breakdown-and-plan` feature. Phase 1 of that
feature (chapter date ranges) is **kept and renamed**; Phase 2 (admin page ranges +
manual slot builder + per-chapter seed) is **removed from admin scope** — its planner
logic is salvaged and moved teacher-side (D-12).
