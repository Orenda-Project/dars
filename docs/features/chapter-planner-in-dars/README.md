# Chapter Planner in Dars

Merge the standalone **Chapter Planning Engine** (`chapter-planner-app/`) into the dars backend so dars owns intelligent chapter planning directly — no separate process, no HTTP hop, no duplicated planner.

Today dars' `generate_chapter_plan` uses a deterministic **placeholder** (one lesson per topic + a final formative assessment). The standalone app has the real **LLM planner**: given a chapter's topics + SLOs, a subject, a grade, and a period count, it emits exactly `period_count` ordered lesson **Plan Units**, each picking an `lp_type`, grouping topics, and listing the SLOs it covers — every chapter SLO covered. This feature ports that planner into `dars/server/src/dars/breakdown/`, wires it as the engine behind the teacher-app "break it down" flow, exposes a `/plan` endpoint, and deletes the standalone app.

## Documents (read in this order)

1. [01-decision-log.md](01-decision-log.md) — frozen decisions (D-N). **Load-bearing.**
2. [02-data-model.md](02-data-model.md) — slot↔topic relationship the planner writes (no migration; existing tables).
3. [00-glossary.md](00-glossary.md) — terms used in later docs.
4. [03-phase-1-port-planner.md](03-phase-1-port-planner.md) — port planner core + agent-sdk backend + `/plan` endpoint into dars.
5. [04-phase-2-wire-and-delete.md](04-phase-2-wire-and-delete.md) — replace the placeholder in `generate_chapter_plan`; delete `chapter-planner-app/`.
6. [05-reference-planner-contract.md](05-reference-planner-contract.md) — frozen planner I/O contract + prompt, copied from the standalone app.
7. [ONRAMP.md](ONRAMP.md) — cold-start entry point for any future session.

## Document precedence

```
1. 01-decision-log.md         (D-N references are canonical)
2. 02-data-model.md           (slot↔topic ground truth)
3. 00-glossary.md             (terminology)
4. phase docs                 (specs derived from above)
5. running code               (last; code may be stale)
```

This feature adds **no schema and no migration** — a Plan Unit's multi-topic grouping is persisted into the *already-deployed* `class_lesson_slot_topics` join table (see 02-data-model.md). If two docs disagree, the order above wins; surface conflicts, don't silently pick a side.
