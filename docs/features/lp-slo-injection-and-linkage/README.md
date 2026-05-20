# LP ↔ Sub-SLO Injection and Linkage

Every generated LP should both (a) be **steered** at request time to cover the sub-SLOs attached to its topic, and (b) be **linked** to those sub-SLOs as the canonical record of intent — independent of whether F3.8's downstream evidence-based tagging confirms them.

Today's behavior:
- The LP Assistant client (`lp_assistant_client.py`) sends `page_content`, `lp_type`, etc. but explicitly omits `custom_prompt`.
- After the LP comes back via webhook, F3.8 (`lp_tagging_service.py`) reads the HTML, asks an LLM which candidate sub-SLOs the LP actually evidences, and writes the *evidenced* subset to `generated_lps.covered_sub_slo_ids`.
- There is no upstream guidance that the LP should cover the topic's sub-SLOs, and no record of which sub-SLOs the LP was *requested* to cover.

This feature adds both directions:
- **Upstream:** when dispatching to LP Assistant, build a `custom_prompt` string listing the topic's sub-SLOs (statement text) and instruct the model to ensure coverage. Send it on the v3 request.
- **Downstream:** persist the *requested* sub-SLOs (the ones we asked for) on the LP at insert time, so the LP is linked to those SLOs from the moment it's enqueued, not only after F3.8 finishes.

Size: **S** — one PR, one phase doc, no new tables. Adds one column (`requested_sub_slo_ids UUID[]`) plus one new field on the request payload; threads the sub-SLO list through the existing dispatch path. Revision-LP path gets the union of prior topics' sub-SLOs.

## Index

1. [00-glossary.md](00-glossary.md) — terms used in the plan docs that aren't already in the v2 rebuild glossary
2. [01-decision-log.md](01-decision-log.md) — design decisions for this feature
3. [02-phase-1-injection-and-linkage.md](02-phase-1-injection-and-linkage.md) — the single execution phase

## Document precedence

```
1. 01-decision-log.md         (D-N references are canonical)
2. The v2 rebuild's 02-data-model.md (this feature adds one column, documented in the phase doc)
3. 00-glossary.md             (terminology)
4. 02-phase-1-*.md            (specs derived from above)
5. running code               (last; code may be stale)
```

If two docs disagree, this is the order. Code is **lowest** authority. Surface conflicts; don't silently pick a side.

## Relationship to the v2 rebuild plan

This is a small follow-on to Phase 3 (Generation Pipeline) of the v2 rebuild at `docs/plans/2026-05-15-dars-v2-rebuild/`. F3.2 (the LP Assistant client) and F3.8 (post-generation tagging) are referenced extensively. Decisions here may add new entries that the rebuild's `01-decision-log.md` should cross-reference once this feature ships — but per the plan-alive rule, this feature's decisions live here.
