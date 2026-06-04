# Phase 3 — Iteration harness + sample chapters

Goal: a rig the user + Claude use to iterate plan quality. Sample chapters (real-ish G1 English and
a Maths one), a CLI/script that runs a chapter through `/plan` and prints the plan readably, a
documented quality rubric, and the UG_LP adapter (D-7) so a unit can be turned into a real LP request
for end-to-end sanity. Independently shippable: running the harness against a sample prints a plan.

## Features

**F-3.1 — Sample chapter fixtures.** *Spec:* `samples/` with ≥2 JSON chapters matching `PlanRequest`:
one G1 English (multi-topic, mixed reading/grammar SLOs incl. an "Adverbs of Time"-style grammar SLO)
and one Maths (concrete/word_problems SLOs). Source topic text from real book content where available;
otherwise representative. *Acceptance:* each sample is a valid `PlanRequest`.

**F-3.2 — Iteration CLI.** *Spec:* `run_plan.py <sample.json>` — POSTs to a running CPE (or calls
`make_chapter_plan` in-process) and pretty-prints the plan: per unit show sequence, lp_type, topics,
SLOs covered, rationale; then a coverage summary (which SLOs covered by which units, any uncovered
flagged). *Acceptance:* running it on each sample prints a readable plan + coverage table.

**F-3.3 — Quality rubric doc.** *Spec:* `QUALITY.md` — the criteria the user + Claude judge plans by:
SLO coverage completeness, sensible lp_type choice, sensible topic merge/split, pedagogical sequencing
(e.g. reading before comprehension_qa), unit-count correctness. Used to drive prompt iteration. *Acceptance:*
doc exists; references concrete examples from sample runs.

**F-3.4 — UG_LP adapter.** *Spec:* `to_lp_request.py` — pure function `PlanUnit → LPGenerationRequest`
dict per the [02-data-model.md](02-data-model.md) mapping table. Harness option to emit the adapted
requests (not call UG_LP — just show what would be sent). *Acceptance:* a unit maps to a valid
`LPGenerationRequest` shape with no missing required fields.

## Notes
This phase has no fixed end — it's the iteration surface. "Done" = the user is satisfied plan quality
is good enough to consider the dars replacement (D-9, a future feature).

## Dependencies
- All of Phase 2 (needs a working planner).
