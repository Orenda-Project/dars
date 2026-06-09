# Teacher Read-Only Syllabus

Lock down the teacher app so a teacher can no longer build or edit their own syllabus. Today the teacher owns their chapter path: they pick chapters from the book, reorder them, remove them, and set per-chapter dates, then break each one down. Going forward the **org's published Syllabus Breakdown is the single source of truth** — it decides which chapters a teacher teaches, in what order, and on what dates. The teacher app shows that path **read-only**, and the teacher's only action is **"Generate chapter plan"** for a chapter, sized by their own timetable (the periods they have, derived from the timetable they maintain).

Mechanically: the per-CST path table (`class_chapters`) stops being teacher-built and is **auto-seeded** from the published org breakdown (chapter + position + dates copied down) the first time the teacher views their syllabus. The four teacher mutation endpoints (pick / reorder / remove / set-dates) and their webapp controls + API-client functions are **deleted**. Generate-chapter-plan is unchanged in behaviour — it still derives the period count from the CST timetable and runs the LLM planner.

## Documents (read in this order)

1. [01-decision-log.md](01-decision-log.md) — frozen decisions (D-N). **Load-bearing.**
2. [02-data-model.md](02-data-model.md) — the tables involved + the auto-seed copy rule (no schema change).
3. [00-glossary.md](00-glossary.md) — terms.
4. [03-phase-1-backend-autoseed.md](03-phase-1-backend-autoseed.md) — auto-seed service + read-only syllabus response; delete the 4 mutation endpoints.
5. [04-phase-2-frontend-readonly.md](04-phase-2-frontend-readonly.md) — rework the syllabus tab to read-only + generate-only; delete the mutation client functions + controls.
6. [ONRAMP.md](ONRAMP.md) — cold-start entry point.

## Document precedence

```
1. 01-decision-log.md         (D-N references are canonical)
2. 02-data-model.md           (table/copy ground truth)
3. 00-glossary.md             (terminology)
4. phase docs                 (specs derived from above)
5. running code               (last; code may be stale)
```

No schema migration: `class_chapters` and `syllabus_chapters` already carry every column needed (book_chapter_id, position, start_date, end_date). If two docs disagree, the order above wins; surface conflicts, don't silently pick a side.
