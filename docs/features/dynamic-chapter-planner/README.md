# Dynamic Chapter Planner

Evolve the one-shot chapter planner into a **re-plannable** system: a class's plan
absorbs real-world disruptions (lost periods / holidays, and reteach after a failed
formative assessment) without overflowing past the fixed year-end, and without nuking
taught history. The mechanism is **buffer-budgeted planning** — plan mandatory content
into ~70–80% of teaching days and interleave droppable *flex* slots per chapter so a
slip is absorbed locally instead of shifting the whole tail.

The realized class slots (`class_lesson_slots` + `class_assessment_slots`) are the live
plan; the global Syllabus Breakdown is a seed read once at break-it-down. Dates are never
stored — the projector derives them at read time, so holidays re-flow automatically. This
feature adds the *mutation* layer (insert / remove / consume-flex slots with a taught-lock),
the buffer-aware planner, and the reteach trigger off `sub_slo_mastery`.

Consolidated source plan: `docs/plans/2026-06-12-dynamic-chapter-planner.md` (kept as the
origin; this folder is the canonical execution surface).

## Documents

1. [00-glossary.md](00-glossary.md) — terms (flex slot, mandatory budget, completion target, taught-lock, reteach).
2. [01-decision-log.md](01-decision-log.md) — D-N decisions; **read this first**, it's load-bearing.
3. [02-data-model.md](02-data-model.md) — schema deltas (`origin`, `reteach_for_sub_slo_id`, `flex`).
4. [03-phase-1-slot-mutation.md](03-phase-1-slot-mutation.md) — migration + `slot_mutation_service` + taught-lock + sqlite tests.
5. [04-phase-2-buffer-planner.md](04-phase-2-buffer-planner.md) — flex/mandatory tagging + buffer-budgeted planner.
6. [05-phase-3-reteach-trigger.md](05-phase-3-reteach-trigger.md) — mastery-threshold → suggestion → confirm → consume-flex/insert → LP.
7. [ONRAMP.md](ONRAMP.md) — single entry point for a fresh agent picking up the work.

## Document precedence

```
1. 01-decision-log.md         (D-N references are canonical)
2. 02-data-model.md           (schema is ground truth)
3. 00-glossary.md             (terminology)
4. phase docs                 (specs derived from above)
5. running code               (last; code may be stale)
```

If two docs disagree, this is the order. Code is **lowest** authority.
