# Reference — Planner LLM Contract (frozen)

The exact prompt shape and JSON output the Chapter Planner expects from the LLM (D-5). The same prompt/output is used regardless of backend — both the production API-key backend and the development Agents SDK backend (D-10) call `PlannerLLM.complete(system, user)` and return the JSON below. Freeze this so future agents don't re-derive it. Tune wording during execution if outputs are poor, but keep the JSON schema stable (the parser + validator depend on it).

## Inputs given to the model

- Subject code, grade.
- Period count (the hard target — output must have exactly this many items).
- The chapter's topics, in book order: for each, `topic_id` (UUID), `title`, and `topic_text` (may be truncated to a sane char budget — note any truncation).
- For each topic, its sub-SLOs: `sub_slo_id` (UUID), `code`, `statement`.
- The chapter's SLOs: `code`, `statement` (context for grouping).
- The valid `lp_type` values for this subject (from `is_valid_lp_type`), so the model only emits legal ones.

## System prompt (intent — exact wording tunable)

> You are a curriculum planner. Given a chapter's topics, the sub-SLOs each topic teaches, and a fixed number of teaching periods, produce an ordered plan of exactly N periods. Each period is either a **lesson** (one LP that may combine several thin topics or focus on part of a dense one) or a **formative assessment** (FA) that checks sub-SLOs already taught. Sequence lessons before the FAs that assess them. Every topic must be taught by at least one lesson. Choose an `lp_type` for each lesson only from the allowed list. Cover all the chapter's sub-SLOs across the lessons. Place FAs where they best consolidate learning — you decide how many and where. Output **strict JSON only**, no prose.

Strict-JSON instruction + "no markdown fences" line included; parser strips fences defensively anyway.

## Output JSON schema

```json
{
  "items": [
    {
      "kind": "lp",
      "topic_ids": ["<uuid>", "..."],
      "lp_type": "<one of the allowed lp_types>",
      "sub_slo_ids": ["<uuid>", "..."]
    },
    {
      "kind": "fa",
      "topic_ids": ["<uuid>", "..."],
      "sub_slo_ids": ["<uuid>", "..."]
    }
  ]
}
```

- `items` length **must equal the period count**.
- `lp` items: `topic_ids` ≥1, `sub_slo_ids` ≥1, `lp_type` from the allowed set.
- `fa` items: `topic_ids`/`sub_slo_ids` must be subsets of the chapter's.
- UUIDs must be ones supplied in the input (no invention).

The validator (F-1.2 / D-3) enforces all of the above; any violation → deterministic fallback. No summative items (D-6).

## Notes

- The model never sees DB connections or writes anything — it returns JSON that the service maps to `ChapterPlan`.
- `page_content` and `sub_slo_statements` for the actual LP Assistant call are assembled by dars from the `topic_ids`/`sub_slo_ids` the model returns (see `06-reference-downstream-contracts.md`) — the model does not produce lesson-plan prose.
