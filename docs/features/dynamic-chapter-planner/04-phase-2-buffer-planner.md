# Phase 2 — Buffer-budgeted planner

Make the planner produce mandatory content into a fraction of the teaching days and fill the
rest with interleaved flex slots (D-3, D-4). Independently shippable: break-it-down now emits
flex slots; reteach (Phase 3) consumes them.

## F-2.1 — Flex in the planner output model

**Spec:** `planner_models.PlanUnit` gains a way to mark a unit droppable — either
`slot_type='flex'` or a `flex: bool` on lesson units (decide at phase start; lean `flex: bool`
to avoid touching the `slot_type` enum + its validators). Flex units are revision/consolidation
lessons (no FA, no summative).
**Acceptance:** model validates; a flex unit carries `lp_type='revision'`, `flex=true`.

## F-2.2 — Completion-target knob

**Spec:** introduce `completion_target` (org default ~0.8, optional per-CST override) per
[02-data-model.md](02-data-model.md). `chapter_plan_service` reads it when building the plan
request and computes the per-chapter mandatory budget = `round(chapter_days * target)`.
**Acceptance:** changing the knob changes the mandatory/flex split for a fresh break-it-down.

## F-2.3 — Buffer distribution

**Spec:** planner prompt (`planner_prompts.py`) + `chapter_plan_service` change the contract
from "fill `period_count`" to "plan mandatory content into the mandatory budget, then add flex
slots interleaved after topic clusters to reach `period_count`." Per-chapter flex proportional
to chapter length; rounding leftovers form the thin shared remainder pool placed end-of-term
(D-4). Persist flex lessons with `flex=true`, `origin='breakdown'`.
**Acceptance:** a planned chapter shows mandatory lessons + FAs plus interleaved flex revision
slots; total still equals `period_count` (1 slot = 1 day); flex count ≈ `(1-target)` share.

## F-2.4 — Tests

**Spec:** extend planner tests — flex units parse/validate; budget math splits correctly for
representative chapter sizes; short chapters round flex to zero.
**Acceptance:** green; pure-planner tests need no DB.

## Dependencies

Depends on Phase 1 (the `flex` column). Independent of Phase 3.

## Open question (resolve at phase start)

`completion_target` home: per-CST column vs org settings row vs both. Leaning org default +
optional per-CST override. One `AskUserQuestion` if still ambiguous.
