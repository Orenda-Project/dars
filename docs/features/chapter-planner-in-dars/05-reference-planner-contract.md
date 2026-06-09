# Reference — Planner I/O Contract & Prompt (frozen)

Copied from `chapter-planner-app/` as of 2026-06-09. Ground truth for the planner's behaviour. The port must reproduce these exactly (D-5).

## Input — PlanRequest

```jsonc
{
  "subject": "Eng",          // ∈ VALID_LP_TYPES keys; drives allowed lp_types
  "grade": 1,                // 1..5
  "curriculum": "ICT",       // passed through to UG_LP
  "period_count": 3,         // > 0; number of Plan Units to produce
  "chapter": {
    "title": "Chapter 1 — Myself",
    "topics": [              // ≥1 topic, unique ids
      {
        "id": "t1",
        "topic_text": "Greetings ...",
        "slos": [            // ≥1 SLO; same id may repeat across topics IF same statement
          {"id": "s1", "statement": "Student can greet others"}
        ]
      }
    ]
  }
}
```

Validation (pydantic, from `models.py`): `period_count > 0`; `1 ≤ grade ≤ 5`; `subject ∈ VALID_LP_TYPES`; ≥1 topic; ≥1 SLO per topic; topic ids unique; an SLO id may appear on multiple topics only with an identical statement.

## Output — ChapterPlan

```jsonc
{
  "subject": "Eng", "grade": 1, "curriculum": "ICT", "period_count": 3,
  "units": [
    {
      "sequence": 1,                 // 1..period_count, a permutation
      "lp_type": "reading",          // ∈ VALID_LP_TYPES[subject]
      "topic_ids": ["t1"],           // ordered, ≥1
      "slo_ids": ["s1"],             // ≥1, ⊆ chapter SLOs
      "topic_text": "Greetings ...", // member topics joined in topic_ids order — CPE fills this, NOT the LLM
      "rationale": "one sentence"
    }
  ]
}
```

## D-8 invariants (validate_plan)

Returns the first violation message, or None:
- (a) exactly `period_count` units
- (b) every chapter SLO covered by ≥1 unit
- (c) each unit's `lp_type` ∈ `VALID_LP_TYPES[subject]`
- (d) each unit: ≥1 `topic_id` (all real), ≥1 `slo_id` (all real)
- (e) `sequence` values are a permutation of `1..period_count`

No repair, no retry, no fallback. A violation raises `PlanValidationError`; bad JSON raises `PlanParseError`; LLM transport failure raises `PlannerLLMError`.

## VALID_LP_TYPES (copied from UG_LessonPlan/config.py, 2026-06-03)

```python
VALID_LP_TYPES = {
    "Eng":      ["reading", "comprehension_word_meanings", "comprehension_qa", "grammar", "creative_writing", "revision"],
    "Urdu":     ["reading", "comprehension_word_meanings", "comprehension_qa", "grammar", "creative_writing", "revision"],
    "Maths":    ["concrete", "pictorial_and_abstract", "word_problems", "revision"],
    "Science":  ["revision"],
    "GK":       ["revision"],
    "Islamiat": ["revision"],
    "SST":      ["revision"],
}
```

## System prompt (frozen, from prompts.py)

> You are a curriculum planning engine. Given a chapter's topics (each with source text and the SLOs it teaches), a subject, and a fixed number of teaching periods, produce an ordered plan of EXACTLY that many lesson Plan Units. Each unit is one lesson plan.
>
> Hard rules:
> 1. Return EXACTLY `period_count` units. `sequence` is 1..period_count, each used once.
> 2. A unit may combine several thin topics or focus on part of a dense one — you decide the boundaries. Each unit lists the `topic_ids` it draws from (>=1) and the `slo_ids` it teaches (>=1).
> 3. Every SLO in the chapter must be taught by at least one unit (full coverage). Only reference topic_ids and slo_ids that were given to you — never invent ids.
> 4. Choose `lp_type` for each unit ONLY from the provided allowed list. Pick the type that best fits that unit's topics and SLOs.
> 5. Give a one-sentence `rationale` per unit.
>
> Return STRICT JSON ONLY — no prose, no markdown fences. The exact shape:
> `{"units": [{"sequence": 1, "lp_type": "<allowed>", "topic_ids": ["<id>"], "slo_ids": ["<id>"], "rationale": "<one sentence>"}]}`

User prompt = JSON of `{subject, grade, period_count, allowed_lp_types, chapter_title, topics:[{id, topic_text, slos:[{id, statement}]}]}`. `recommended_lp_type` is intentionally NOT passed.

## agent-sdk backend (from planner_llm.py)

`AgentSdkPlannerLLM.complete(system, user)` lazy-imports `claude_agent_sdk.{query, ClaudeAgentOptions}`, calls `query(prompt=user, options=ClaudeAgentOptions(system_prompt=system))`, and concatenates `message.content[].text` blocks (D-13: text is in content blocks, not `message.text`). Empty response → `PlannerLLMError`. Same pattern as `book_import_service` in the server.

## topic_text resolution

`_resolve_topic_text(topic_ids, request)` = member topics' `topic_text` joined with `"\n\n"` in `topic_ids` order. CPE fills `PlanUnit.topic_text` from this; the LLM never echoes topic text back.
