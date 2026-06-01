# Class Timeline View — teacher app

**What this feature does.** Replaces the two separate Lessons and Assessments tabs in the teacher app's per-class view with a single **unified, dated timeline**. Lessons and assessments are interleaved in the exact order the class teaches them (by `position`), each stamped with its **projected calendar date** from the backend projector, grouped by chapter (with a week sub-rhythm visible), and marked with a **"you are here"** indicator on the current slot. Generation status (LP/exam) is de-emphasised into a quiet signal rather than competing primary content. Conflict/overflow flags from the projector are surfaced so a teacher (or the demo viewer) can see when a slot can't be placed.

The root problem this fixes: today the UI splits one teaching sequence into two parallel `position`-ordered lists, discarding the interleaving and the calendar dates that the backend projector already computes. A teacher cannot see "lesson, lesson, formative assessment, lesson…" as it actually unfolds, nor when any of it happens.

This is delivered in two phases: a new backend `GET /api/v2/csts/{cst_id}/timeline` endpoint that runs the projector and returns merged, dated, status-bearing slots; then a frontend Timeline tab that renders it and becomes the primary lessons/assessments surface.

## Documents

1. [00-glossary.md](00-glossary.md) — terms used across these docs
2. [01-decision-log.md](01-decision-log.md) — canonical architectural decisions (read first)
3. [03-phase-1-timeline-endpoint.md](03-phase-1-timeline-endpoint.md) — backend merged timeline endpoint
4. [04-phase-2-timeline-tab.md](04-phase-2-timeline-tab.md) — frontend unified timeline tab
5. [ONRAMP.md](ONRAMP.md) — single entry point for any agent picking this up (written after plan approval)

No `02-data-model.md`: this feature adds **no schema** — the projector and slot tables already exist.

## Document precedence

```
1. 01-decision-log.md         (D-N references are canonical)
2. 00-glossary.md             (terminology)
3. phase docs                 (specs derived from above)
4. running code               (last; code may be stale)
```

If two docs disagree, this order wins. Code is lowest authority. Surface conflicts; don't silently pick a side.
