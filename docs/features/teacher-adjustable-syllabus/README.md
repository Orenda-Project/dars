# Teacher-Adjustable Syllabus (suggestion-led)

Reframes the syllabus from a binding plan into a **suggestion**, and gives each class
its own real **teaching path**.

Today a class is implicitly bound to the published **global** Syllabus Breakdown for its
(curriculum, grade, subject), and the teacher-app derives "what's today" from generated
slots. This feature makes the global syllabus **advisory** and lets the teacher drive
their own path, chapter by chapter:

- The class records its **own ordered list of chapters** it is teaching (`class_chapters`),
  each with a status: **yet-to-start / in-progress / done** (derived from taught LPs).
- The global syllabus only **suggests** what to teach next. At session start (nothing
  taught), the app shows *"Nothing planned. The default suggests Chapter 1 — what would
  you like to teach?"* with Ch 1 recommended but **any** chapter selectable.
- **Picking a chapter records the choice** (appends it to the class path); **breaking it
  down** into Chapter-Plan slots stays a separate explicit step.
- The teacher can **reorder upcoming** (yet-to-start) chapters; chapters that are
  in-progress/done are **locked** (the past is immutable).

This **dissolves the "half-taught chapter" problem**: there's no rigid plan to diverge
from. A partially-taught chapter is simply `in-progress`; choosing a different chapter
next is a normal pick. Taught history is never rewritten.

---

## Documents

1. [`00-glossary.md`](00-glossary.md) — terms (suggestion, class path, class_chapters, chapter status, lock).
2. [`01-decision-log.md`](01-decision-log.md) — frozen decisions D-1….
3. [`02-data-model.md`](02-data-model.md) — `class_chapters` table + status derivation.
4. [`03-phase-1-class-chapters.md`](03-phase-1-class-chapters.md) — `class_chapters` table, pick/record + status, suggestion resolution.
5. [`04-phase-2-reorder-lock-breakdown.md`](04-phase-2-reorder-lock-breakdown.md) — reorder upcoming + lock taught; wire break-it-down to a chosen chapter.
6. [`05-phase-3-teacher-ui.md`](05-phase-3-teacher-ui.md) — teacher-app: suggestion prompt, pick, chapter statuses, reorder.
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

## Builds on

The shipped `syllabus-breakdown-and-teacher-chapter-plan` (global syllabus + teacher
Chapter Plan + class slots). This feature does **not** reintroduce per-class syllabus
*scope* (an earlier draft of this plan did — superseded by the suggestion-led model,
D-1). The global stays global and advisory; the class's path lives in `class_chapters`.
