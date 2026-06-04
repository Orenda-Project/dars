# Data model / contracts — Chapter Planning Engine

CPE is **stateless** — it persists nothing. The "data model" is the request/response contract and
the internal schema the LLM must produce. These are ground truth (precedence #2). Schemas given as
Pydantic-shaped pseudocode; field names are canonical.

## Input — `POST /plan`

```jsonc
{
  "subject": "Eng",          // ∈ VALID_LP_TYPES keys; drives allowed lp_types (D-5)
  "grade": 1,                // 1..5; passed through to UG_LP later (D-7)
  "curriculum": "ICT",       // default "ICT"; passed through to UG_LP
  "period_count": 3,         // > 0; number of Plan Units to produce (D-8a)
  "chapter": {
    "title": "Chapter 1 — Myself",
    "topics": [
      {
        "id": "t1",                      // stable within request; LLM references these
        "topic_text": "…page content…", // source text for the topic
        "slos": [
          { "id": "s1", "statement": "Student can greet others" },
          { "id": "s2", "statement": "Student can state their name" }
        ]
      }
      // … more topics
    ]
  }
}
```

Validation on input: `period_count > 0`; `subject ∈ VALID_LP_TYPES`; `1 ≤ grade ≤ 5`; ≥1 topic; every topic ≥1 SLO; topic ids unique; SLO ids unique across the chapter.

## Output — `200 ChapterPlan`

```jsonc
{
  "subject": "Eng",
  "grade": 1,
  "curriculum": "ICT",
  "period_count": 3,
  "units": [
    {
      "sequence": 1,                       // 1..period_count, permutation (D-8e)
      "lp_type": "reading",                // ∈ VALID_LP_TYPES[subject] (D-5)
      "topic_ids": ["t1"],                 // ordered, ≥1 (D-4)
      "slo_ids": ["s1", "s2"],             // ≥1, ⊆ chapter SLOs (D-8b,d)
      "topic_text": "…concatenated…",      // member topics' text, joined in topic_ids order (D-4)
      "rationale": "Intro reading to anchor greetings before grammar."
    }
    // … period_count units total
  ]
}
```

## Internal — what the LLM returns (parsed, then validated)

The LLM is prompted to return **strict JSON only** matching the `units` array above (sequence,
lp_type, topic_ids, slo_ids, rationale). CPE resolves `topic_text` itself from `topic_ids` (the
LLM does not echo full text back — keeps tokens down and avoids drift). `PlanValidator` (D-8) runs
on the parsed units before they're returned.

## Adapter to UG_LessonPlan (D-7) — not an endpoint, a documented mapping

Each `PlanUnit` → one `LPGenerationRequest` (see [06-reference-ug-lp-input.md](06-reference-ug-lp-input.md)):

| PlanUnit / request field | → LPGenerationRequest field |
|--------------------------|------------------------------|
| `subject`                | `subject` |
| `grade`                  | `grade` |
| `curriculum`             | `curriculum` |
| `lp_type`                | `lp_type` |
| `topic_text`             | `page_content` |

`page_number` is omitted (content supplied directly). The adapter is built in Phase 3 only as a
convenience for the iteration harness — production wiring is D-9 (out of scope).

## Error contract

| Condition | Status | Body |
|-----------|--------|------|
| Input validation fails | 422 | FastAPI validation detail |
| LLM call fails | 502 | `{"detail": "planner LLM error: …"}` |
| Plan fails PlanValidator | 422 | `{"detail": "invalid plan: <first violation>"}` |
