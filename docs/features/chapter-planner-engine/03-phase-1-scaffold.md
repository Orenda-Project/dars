# Phase 1 — Standalone service scaffold

Goal: a runnable, independent FastAPI app at `dars/chapter-planner-app/` with health, the `/plan`
route returning a stubbed/echo response, request/response Pydantic models matching
[02-data-model.md](02-data-model.md), config (subject→lp_type table), structured logging, and a
minimal static playground. **No real LLM call yet** — that's Phase 2. This phase is independently
runnable and shippable.

Independently shippable: `uvicorn main:app` boots; `/health` is green; `/plan` validates input and
returns a deterministic stub plan (round-robins topics into `period_count` units) so the contract
and playground are exercisable end-to-end before the LLM lands.

## Features

**F-1.1 — Directory + app skeleton.** *Spec:* Create `dars/chapter-planner-app/` with `main.py`
(FastAPI app, CORS, `/health`), `config.py` (`VALID_LP_TYPES` copied verbatim from UG_LP per D-5,
`VALID_SUBJECTS`, env loading), `logging_config.py` (`get_logger`, structured), `requirements.txt`
(fastapi, uvicorn, pydantic, python-dotenv, claude-agent-sdk), `README.md` (quick start + run cmd),
`.env.example`. Mirror the UG_LP file layout. *Acceptance:* `uvicorn main:app --port 4100` boots;
`GET /health` → `{"status":"ok"}`. Logs entry/exit at INFO.

**F-1.2 — Pydantic contracts.** *Spec:* In `models.py` define `PlanRequest`, `Chapter`, `Topic`,
`SLO`, `ChapterPlan`, `PlanUnit` exactly per [02-data-model.md](02-data-model.md). Input validators:
`period_count > 0`, `subject ∈ VALID_LP_TYPES`, `1 ≤ grade ≤ 5`, ≥1 topic, each topic ≥1 SLO, unique
topic ids, unique SLO ids. *Acceptance:* invalid payloads → 422 with clear detail; valid payload parses.

**F-1.3 — `/plan` stub endpoint.** *Spec:* `POST /plan` accepts `PlanRequest`, returns a `ChapterPlan`
built by a deterministic stub (`stub_planner.py`): round-robin assign topics across `period_count`
units, lp_type = first allowed for subject, slo_ids = the assigned topics' SLOs, `topic_text`
resolved. The stub exists only to exercise the contract; Phase 2 replaces it. *Acceptance:* a 3-period
request returns 3 units, all chapter SLOs covered, passes the (Phase-2) validator shape.

**F-1.4 — Static playground.** *Spec:* `static/index.html` served at `/` — a textarea for the JSON
request, a "Plan" button hitting `/plan`, and a readable render of the returned units (sequence,
lp_type, topics, SLOs, rationale). Pre-fill with one sample G1 English chapter. *Acceptance:* opening
`/` and clicking Plan shows the stub plan rendered.

## Dependencies
- F-1.2 before F-1.3 (endpoint uses the models).
- F-1.4 after F-1.3 (playground hits the live endpoint).
