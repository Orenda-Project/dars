# Phase 1 — Planner Core (pure, no DB)

**Goal:** A self-contained, independently-testable planning brain that turns (chapter material, SLOs/sub-SLOs, period count) into a validated `ChapterPlan`, with the deterministic fallback wired in. No DB, no endpoint changes yet — Phase 1 ships behind tests only and is exercised by Phase 2.

Shippable to staging on its own: the new module compiles, unit tests pass, nothing else calls it yet.

New module: `server/src/dars/breakdown/chapter_planner_service.py` (sibling of `chapter_plan_service.py`, which it will eventually front).

---

## F-1.1 — Plan data structures

**Spec.** Define the planner's I/O dataclasses/Pydantic models:

- `PlanInputs`: `subject_code: str`, `period_count: int`, `topics: list[TopicInput]` (each `topic_id`, `title`, `topic_text`, `sub_slos: list[SubSloInput]`), `chapter_slos: list[SloInput]` (statement + recommended_lp_type, for context). Pure values — Phase 2 builds this from DB rows.
- `PlanItem`: discriminated by `kind: 'lp' | 'fa'`.
  - LP: `topic_ids: list[UUID]` (ordered, ≥1), `lp_type: str`, `sub_slo_ids: list[UUID]`.
  - FA: `topic_ids: list[UUID]`, `sub_slo_ids: list[UUID]`.
- `ChapterPlan`: `items: list[PlanItem]`, `source: 'llm' | 'fallback'`.

**Acceptance.** Models import; an LP item requires ≥1 topic and ≥1 sub-SLO at construction; `ChapterPlan` round-trips to/from the JSON shape in `05-reference-planner-llm-contract.md`.

## F-1.2 — PlanValidator (D-3)

**Spec.** Pure `validate_plan(plan: ChapterPlan, inputs: PlanInputs) -> list[str]` returning a list of violation strings (empty == valid). Enforce D-3 invariants (a)–(f): item count == `period_count`; every input topic in ≥1 LP unit; every LP `lp_type` passes `is_valid_lp_type(subject_code, lp_type)`; every LP ≥1 topic & ≥1 sub-SLO; every FA's `topic_ids`/`sub_slo_ids` ⊆ chapter's; ≥1 LP unit, and ≥1 FA item when `period_count` leaves room for one.

**Acceptance.** Unit tests: a hand-built valid plan returns `[]`; each invariant has a test that trips exactly one violation. No DB. Covers the period-count mismatch, bad lp_type, hallucinated topic id, empty LP unit, FA covering an out-of-chapter sub-SLO.

## F-1.3 — `PlannerLLM` interface + two backends (D-5, D-10)

**Spec.** Define `PlannerLLM` protocol: `async complete(system: str, user: str) -> str`. Two backends:
- `ApiKeyPlannerLLM` — wraps `breakdown/llm_client.call_llm` (`ANTHROPIC_API_KEY`). **Production.**
- `AgentSdkPlannerLLM` — wraps `claude-agent-sdk` against the dev's Claude Code OAuth session. **Development only.** Lazy-import the SDK so production never requires it installed; `claude-agent-sdk` is added as a dev/optional dependency in `pyproject.toml`.
A factory `get_planner_llm(settings) -> PlannerLLM` selects by `settings.planner_llm_backend` (default = API key; production never sets `agent_sdk`).

Then `async plan_with_llm(inputs: PlanInputs, *, llm: PlannerLLM) -> ChapterPlan` builds the prompt per `05-reference-planner-llm-contract.md`, calls `llm.complete(...)`, strips ```json fences, parses to `ChapterPlan` with `source='llm'`. Raises typed `PlannerLLMError` on transport/parse failure (caller catches → fallback). Structured logging: entry with `subject/period_count/topic_count/backend`, exit with `item_count`, errors at ERROR with `exc_info=True`.

**Acceptance.** Unit test injecting a fake `PlannerLLM` returning canned JSON → correct `ChapterPlan`. Fenced JSON parses. Malformed JSON raises `PlannerLLMError`. `get_planner_llm` returns the API-key backend by default and the SDK backend only when the dev flag is set. No real network; SDK import is not required to run the suite.

## F-1.4 — Deterministic fallback adapter

**Spec.** `plan_deterministic(inputs: PlanInputs) -> ChapterPlan` reuses the existing pure planners: `allocate_chapter_days(period_count, topic_count, fa_cadence=5, sa_per_chapter=0)` (D-6) + `plan_chapter_slots(...)` + `pick_lp_type(...)` per topic, then maps the resulting `PlannedSlot`s into `ChapterPlan` `PlanItem`s — one-topic LP units, FA items with their `covered_topic_ids`, dropping any SA/revision-vs-FA distinctions per D-6 (revision slots map to an LP unit of `lp_type='revision'` if the existing path emits them, or are omitted — match what `plan_chapter_slots` returns with `sa_per_chapter=0`). `source='fallback'`. Each LP unit's `sub_slo_ids` = the sub-SLOs mapped to its topic.

**Acceptance.** Unit test: given inputs with K topics and P periods, the fallback returns exactly P items, all topics covered, `source='fallback'`, and the result passes `validate_plan`. (Self-consistency: the fallback must always satisfy its own validator.)

## F-1.5 — Orchestrator: `make_chapter_plan`

**Spec.** `async make_chapter_plan(inputs, *, llm: PlannerLLM) -> ChapterPlan`:
1. Try `plan_with_llm`. On `PlannerLLMError` → fallback (log WARNING "llm unavailable").
2. Run `validate_plan` on the LLM plan. If violations → log WARNING with the joined reasons + "falling back" → `plan_deterministic`.
3. Else return the LLM plan.
The fallback result is returned as-is (it's validator-clean by F-1.4); if it somehow fails validation, log ERROR and still return it (never block the teacher — D-1).

**Acceptance.** Unit tests with an injected fake `PlannerLLM`: (a) valid LLM JSON → `source='llm'`; (b) LLM raises → `source='fallback'`; (c) LLM returns count-mismatch JSON → `source='fallback'` + WARNING logged. No DB.

---

## Dependencies

- F-1.2 depends on F-1.1. F-1.3, F-1.4 depend on F-1.1. F-1.5 depends on F-1.2/1.3/1.4.
- Reuses (no change): `lp_type_heuristics.pick_lp_type`, `chapter_plan_service.allocate_chapter_days` / `plan_chapter_slots`, `v2_api.lp_types.is_valid_lp_type`, `breakdown/llm_client.call_llm` (wrapped by the API-key `PlannerLLM` backend, D-10).
- Adds: `claude-agent-sdk` as a dev/optional dependency (D-10), lazily imported by the SDK backend only.

## Out of scope for Phase 1

DB reads/writes, the migration, the endpoint, multi-topic persistence — all Phase 2.
