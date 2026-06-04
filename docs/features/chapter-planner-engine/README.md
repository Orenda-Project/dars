# Chapter Planning Engine (CPE) — v2 standalone service

The Chapter Planning Engine is a **standalone, LLM-powered FastAPI service** — built in the
same mould as `UG_LessonPlan` and `UG_EG`. It takes a **Chapter** (its topics, each mapped to
SLOs) plus a **period count**, and returns a **Chapter Plan**: an ordered sequence of teaching
units that together cover the chapter's SLOs across the given number of periods. Each unit is a
spec for *which* lesson plan to make next (its `lp_type`, its topic text, its target SLOs) — it
is **not** the lesson plan itself. The actual LP is generated downstream by feeding each unit
into `UG_LessonPlan`'s `/generate-lp` endpoint as the input.

The service runs and is iterated **in isolation** for now (tested by the user + Claude, not wired
into the dars backend or frontend). The long-term goal is to **replace the deterministic
chapter-plan path currently plugged into dars** (the `intelligent-chapter-planner` feature's
`make_chapter_plan` flow) with this LLM planner. The output contract is therefore designed to be
dars-compatible from day one even while the app stands alone.

## Documents (read in this order)

1. [01-decision-log.md](01-decision-log.md) — frozen architectural decisions (`D-N`); **load-bearing**, read first
2. [00-glossary.md](00-glossary.md) — every capitalised term used in these docs
3. [02-data-model.md](02-data-model.md) — request/response/internal schemas (this service is stateless; "data model" = the contracts)
4. [03-phase-1-scaffold.md](03-phase-1-scaffold.md) — Phase 1: standalone FastAPI scaffold + health + static playground
5. [04-phase-2-planner-core.md](04-phase-2-planner-core.md) — Phase 2: LLM planner core (prompt, Agents-SDK backend, validator)
6. [05-phase-3-iteration-harness.md](05-phase-3-iteration-harness.md) — Phase 3: eval/iteration harness + sample chapters
7. [06-reference-ug-lp-input.md](06-reference-ug-lp-input.md) — frozen UG_LessonPlan `/generate-lp` request shape (the output target)
8. [ONRAMP.md](ONRAMP.md) — single entry point for a fresh agent picking this up cold

## Document precedence

```
1. 01-decision-log.md         (D-N references are canonical)
2. 02-data-model.md           (contracts are ground truth)
3. 00-glossary.md             (terminology)
4. phase docs                 (specs derived from above)
5. running code               (last; code may be stale)
```

If two docs disagree, this order wins. Code is lowest authority. Surface conflicts; don't silently pick a side.
