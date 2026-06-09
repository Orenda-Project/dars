# Phase 1 — Port the planner core into dars

Bring the CPE planner (models, prompts, parse/validate, agent-sdk backend) into `dars/server/src/dars/breakdown/`, and expose a thin `/plan` endpoint. No wiring into `generate_chapter_plan` yet (that's Phase 2). No persistence (D-6). Independently shippable: ships a working, tested `/plan` endpoint that dars didn't have before.

Bead: `feat-chapter-planner-in-dars-phase-1-port`.

## F1.1 — Planner models

**Spec:** Add the planner pydantic models to `breakdown/`. Either a new `breakdown/planner_models.py` or fold into an existing models module — match the breakdown package's convention. Port `SLO`, `Topic`, `Chapter`, `PlanRequest`, `PlanUnit`, `ChapterPlan` from `chapter-planner-app/models.py` verbatim (pydantic v2). Reuse dars' subject/lp_type source rather than introducing a parallel constant if one already exists in `breakdown` (check `lp_type_heuristics`/`lp_types`); otherwise port `VALID_LP_TYPES` (see 05-reference, copied from UG_LP).
**Acceptance:** Models import cleanly; the validators from the reference doc (period_count>0, grade 1..5, subject membership, ≥1 topic, ≥1 SLO/topic, unique topic ids, SLO-id/statement consistency) all fire. Unit tests cover each validator.

## F1.2 — Prompts

**Spec:** Port `build_system_prompt` / `build_user_prompt` from `chapter-planner-app/prompts.py` verbatim (frozen system prompt in 05-reference). Live alongside the planner core, not in `breakdown/prompts/` unless that's the established home for prompt builders.
**Acceptance:** `build_user_prompt(req)` emits the JSON payload in the reference doc; `recommended_lp_type` is NOT included. Snapshot/string test on the system prompt.

## F1.3 — agent-sdk LLM backend (D-2)

**Spec:** Port `AgentSdkPlannerLLM` from `chapter-planner-app/planner_llm.py` into `breakdown/planner_llm.py`. Keep the `PlannerLLM` Protocol, the lazy SDK import, the D-13 content-block extraction, and `PlannerLLMError`. Align with how `v2_api/book_import_service.py` already imports/uses `claude-agent-sdk` (same import names, same `ClaudeAgentOptions` object). Use `logging.getLogger(__name__)`, structured INFO entry/exit + ERROR exc_info per CLAUDE.md rule 11.
**Acceptance:** Backend boots without the SDK installed (lazy import); a `/plan` call with the SDK present returns text; missing SDK → `PlannerLLMError` with the install hint.

## F1.4 — Planner core (parse + validate + build)

**Spec:** Port `chapter-planner-app/planner.py`: `_extract_json`, `parse_plan_units`, `validate_plan` (D-8 invariants), `_resolve_topic_text`, `make_chapter_plan`. Behaviour unchanged (D-5): no repair/retry/fallback. `PlanParseError` / `PlanValidationError` / `PlannerLLMError` preserved.
**Acceptance:** Port the standalone app's planner tests (`chapter-planner-app/tests/`) into `server/tests/` and adapt imports. All pass. The D-8 invariants each have a failing-case test. Tests use a stub `PlannerLLM` (no real LLM call) — port `stub_planner.py` if it's the test double.

## F1.5 — `/plan` endpoint (D-4, D-6)

**Spec:** Add a v2_api endpoint (e.g. `router_planner.py` or fold into an existing breakdown/admin router — match conventions) that accepts a `PlanRequest` body and returns a `ChapterPlan`. Pure transform: no DB write (D-6). Error mapping consistent with the standalone `main.py`: `PlannerLLMError`→502, `PlanParseError`/`PlanValidationError`→422, pydantic validation→422. Structured logging on entry/exit. Respect dars' auth pattern for v2_api endpoints (client_id / API key as the rest of v2_api uses) — do NOT ship an unauthenticated endpoint; check how sibling routers authenticate.
**Acceptance:** `POST /…/plan` with the reference request returns a valid ChapterPlan (mocked LLM in tests). A malformed body → 422. An LLM stub returning bad JSON → 422. Endpoint is registered in the app router and appears in OpenAPI.

## F1.6 — Dependencies & config

**Spec:** Ensure `claude-agent-sdk` is in the server's dependencies (it already is, per `book_import_service`; confirm in `pyproject`/lock). No new env vars — the SDK uses the dev OAuth session like book import. `VALID_LP_TYPES` is code, not config.
**Acceptance:** `uv run pytest` green; server boots; no new required env var.

## Notes from execution
_(appended during the phase as needed — scope changes, follow-ups)_
