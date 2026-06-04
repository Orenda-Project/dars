# Intelligent Chapter Planner

> **STATUS (2026-06-03, D-17): removed from the Dars backend.** The intelligent LLM planner shipped (#108) but is not yet production-ready (see `PLANNER_REPORT.md`). The backend `/plan` break-down has been reverted to a simple deterministic **placeholder** (one lesson per topic + one final formative assessment). The intelligent planner is being rebuilt/iterated as an **independent, locally-testable service** and will be re-integrated once ready. This folder + `PLANNER_REPORT.md` are the design record for that rebuild. See decision **D-17**.

Today the "break it down" flow (`POST /csts/{cst_id}/chapters/{book_chapter_id}/plan`) turns a chapter into a slot sequence with a **purely deterministic algorithm**: it splits days proportionally by topic count, distributes lessons uniformly across topics in book order, interleaves a formative assessment every N lessons, and picks an `lp_type` per topic from a keyword table. It is mechanical — it does not reason about topic difficulty, coherent LP boundaries, or what each assessment should actually cover.

This feature replaces the planning brain with an **LLM-driven Chapter Planner**. Given a chapter, its SLOs and sub-SLOs, and the number of teaching periods, the planner reasons about the material and emits a concrete plan: a sequence of **LP units** (each an input to the UG LP Assistant — `page_content`, `lp_type`, and the sub-SLO statements it must cover) and **Formative Assessments** (placed intelligently, each covering a chosen set of sub-SLOs/topics). LP units may merge thin topics or split dense ones — they are no longer 1:1 with book topics. The existing deterministic algorithm is kept as a **fallback** when the LLM is unavailable or returns invalid output. Summative assessments are out of scope for this round (FA + LPs only). No new UI — the planner is wired behind the existing `/plan` endpoint and persists class slots exactly as today, so downstream LP/FA generation and the teacher timeline are unchanged.

## Documents (read in this order)

1. [00-glossary.md](00-glossary.md) — terms used throughout
2. [01-decision-log.md](01-decision-log.md) — **load-bearing; read first.** Frozen architectural decisions (D-1…)
3. [02-data-model.md](02-data-model.md) — schema delta (the `class_lesson_slot_topics` join table + cache-key change)
4. [03-phase-1-planner-core.md](03-phase-1-planner-core.md) — the LLM planner service + deterministic fallback (pure, no DB)
5. [04-phase-2-persist-and-wire.md](04-phase-2-persist-and-wire.md) — multi-topic persistence, schema migration, wiring behind `/plan`
6. [05-reference-planner-llm-contract.md](05-reference-planner-llm-contract.md) — frozen LLM prompt + JSON output schema
7. [06-reference-downstream-contracts.md](06-reference-downstream-contracts.md) — LP Assistant v3 + UG_EG v2 request shapes the plan feeds into
8. [ONRAMP.md](ONRAMP.md) — single entry point for a fresh agent picking this up

## Document precedence

If two docs disagree, resolve in this order (code is lowest authority):

1. `01-decision-log.md` — D-N references are canonical
2. `02-data-model.md` — schema is ground truth
3. `00-glossary.md` — terminology
4. phase docs — specs derived from the above
5. running code — last; code may be stale

Surface conflicts; don't silently pick a side.
