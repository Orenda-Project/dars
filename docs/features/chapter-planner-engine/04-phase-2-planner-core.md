# Phase 2 — LLM planner core

Goal: replace the Phase-1 stub with the real LLM planner — prompt construction, the Agents-SDK
backend (D-3), strict-JSON parsing, and `PlanValidator` (D-8). After this phase `/plan` produces a
genuine, validated LLM Chapter Plan. Independently shippable: `/plan` returns LLM plans; on LLM or
validation failure it fails loudly per the error contract (D-2).

## Features

**F-2.1 — `PlannerLLM` interface + Agents-SDK backend.** *Spec:* In `planner_llm.py` define the
`PlannerLLM` protocol (`async complete(system: str, user: str) -> str`) and `AgentSdkPlannerLLM`
wrapping `claude-agent-sdk`. **Apply the in-dars D-13 lessons:** iterate `message.content[]` blocks
and concatenate each block's `.text`; construct `ClaudeAgentOptions(system_prompt=system)` (never a
raw dict). Lazy-import the SDK. *Acceptance:* a live manual call returns model text (verified by the
user/Claude in session).

**F-2.2 — Prompt construction.** *Spec:* In `prompts.py`, `build_system_prompt()` and
`build_user_prompt(request)`. System prompt: the planner's role, the hard rules (exactly
`period_count` units; cover every SLO; choose `lp_type` only from the provided allowed list; may
merge/split topics per D-4; return **strict JSON only**, no prose; the exact units schema). User
prompt: subject, grade, period_count, the allowed lp_type list for the subject, and the chapter's
topics with ids, text, and SLOs (ids + statements). Do **not** pass `recommended_lp_type` (D-5). *Acceptance:*
prompts render for a sample chapter; manual inspection confirms all needed context is present.

**F-2.3 — Parse + `PlanValidator`.** *Spec:* `planner.py::make_chapter_plan(request, llm)`:
call `llm.complete`, parse strict JSON to units, resolve `topic_text` from `topic_ids`, run
`PlanValidator.validate(plan, request)` enforcing D-8 invariants (a)–(e). On parse failure → 502;
on validation violation → 422 with the first violation message. No repair, no retry, no fallback
(D-2). *Acceptance:* a hand-crafted invalid LLM response (wrong unit count / missing SLO / bad
lp_type) is rejected with the right message; a valid one passes.

**F-2.4 — Wire `/plan` to the real planner.** *Spec:* `/plan` injects `AgentSdkPlannerLLM` and calls
`make_chapter_plan`; remove the stub from the default path (keep `stub_planner` importable for tests).
Structured logging: entry with subject/grade/period_count/topic count; exit with unit count + lp_type
distribution; errors at ERROR with `exc_info=True`. *Acceptance:* `/plan` on the seeded G1 English
sample returns a coherent LLM plan (e.g. merges thin topics, picks reading/grammar appropriately,
covers all SLOs) that passes the validator.

**F-2.5 — Fake LLM + unit tests.** *Spec:* `tests/` with a `FakePlannerLLM` returning canned JSON;
tests for the validator (each invariant), the parser, and the endpoint (valid + each failure mode).
*Acceptance:* `pytest` green; no live LLM call in the test suite.

## Dependencies
- F-2.1, F-2.2 before F-2.3 (planner uses both).
- F-2.3 before F-2.4.
