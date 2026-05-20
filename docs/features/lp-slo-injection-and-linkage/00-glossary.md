# Glossary — terms specific to this feature

The v2 rebuild's [00-glossary.md](../../plans/2026-05-15-dars-v2-rebuild/00-glossary.md) defines Topic, SubSLO, LP, GeneratedLP, etc. The terms below are introduced or refined for this feature only.

### Requested sub-SLOs

The sub-SLOs the system told LP Assistant the LP should cover when it dispatched the request. Derived deterministically from the slot's `topic_id` via the `topic_sub_slos` join (or, for revision slots, the union over prior-topic sub-SLOs — see *Revision sub-SLO set*).

This is an **intent** record. It is set once at insert time and never changes for a given `generated_lps` row.

Distinct from `covered_sub_slo_ids` (the F3.8 result, which records evidence in the returned HTML).

### Covered sub-SLOs

Already defined in the v2 rebuild plan as the F3.8 output. Restated here only to contrast against *Requested sub-SLOs* — covered ⊆ requested in the happy path, but may diverge if the LLM can't evidence everything or hallucinates extras (which the existing tagging service drops).

### Custom prompt (LP Assistant `custom_prompt` field)

A free-text string the LP Assistant v3 endpoint accepts. When present, LP Assistant appends it to its base prompt so the underlying LLM receives the extra steering. The v2 rebuild plan previously said "do NOT send `custom_prompt`" — this feature reverses that for the specific purpose of sub-SLO steering.

Format we send (frozen by **D-1** in `01-decision-log.md`):

```
After this lesson plan, the following sub-SLOs should be covered:
- <statement 1>
- <statement 2>
...
```

### Revision sub-SLO set

For a revision-type lesson slot (`get_or_generate_revision_lp`), the requested sub-SLO set is the **union** of `topic_sub_slos.sub_slo_id` across all prior topics fed into the revision LP (after the `REVISION_MAX_PRIOR_TOPICS` cap). This matches F3.8's existing candidate-union behavior for revision LPs — consistency between requested and covered candidates lets the two columns be meaningfully compared.
