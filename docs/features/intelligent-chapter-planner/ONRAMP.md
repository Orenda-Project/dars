# Onramp — Intelligent Chapter Planner

You are a Claude agent picking up an in-flight effort. This file is your single entry point. Reading it (and the files it lists) gives you the full context.

You will NOT execute any code, open beads, or write files until you have read everything this file lists.

## Step 1 — Read these files, in this exact order
1. project CLAUDE.md (`/home/hataf/taleemabad/dars/CLAUDE.md`)
2. `docs/features/intelligent-chapter-planner/README.md`
3. `docs/features/intelligent-chapter-planner/00-glossary.md`
4. `docs/features/intelligent-chapter-planner/01-decision-log.md`  ← load-bearing
5. `docs/features/intelligent-chapter-planner/02-data-model.md`
6. The phase file for the active phase (see Step 5): `03-phase-1-planner-core.md` or `04-phase-2-persist-and-wire.md`
7. References: `05-reference-planner-llm-contract.md`, `06-reference-downstream-contracts.md`

## Step 2 — Document precedence
1. `01-decision-log.md` (D-N canonical) → 2. `02-data-model.md` (schema) → 3. `00-glossary.md` → 4. phase docs → 5. running code (lowest). Surface conflicts; don't silently pick a side.

## Step 3 — Who you are in this conversation
- Implement phases sequentially. One bead per phase.
- PRs target `staging`. NEVER `main`.
- After every merge, watch BOTH deploys (server + webapp if relevant) via Railway MCP.
- Treat the decision log as frozen (revise only via a Superseded-by entry + user OK).

## Step 4 — Conversational style (verbatim)
- Default mode: autonomous. Don't pause to confirm understanding.
- No pre-action narration ("I'll now do X").
- One design question at a time via AskUserQuestion with 2–4 options + a Recommended.
- Use sub-agents for exploration (>3 search queries); synthesise yourself.
- Commit + push + open PR is ONE flow.
- After merge, watch deploys (don't wait to be asked).
- Re-read a file before editing if you edited it earlier this session.

## Step 5 — Current state

| Phase | Status | PR | Notes |
|-------|--------|----|-------|
| Phase 1 — Planner core (pure): data structures, PlanValidator, `PlannerLLM` interface + 2 backends, deterministic fallback, orchestrator | 🟢 built, awaiting PR | — | Implemented in worktree `agent-ace8f70793ef27265`; 25 new tests, full suite 182 passed / 34 pre-existing skips. New: `breakdown/chapter_planner_service.py` + `tests/test_chapter_planner_service.py`; `config.py` `planner_llm_backend`; `pyproject.toml` optional extra `planner-agent-sdk`. New decision **D-11**. PR pending. |
| Phase 2 — Persist & wire: migration, build inputs from DB, multi-topic persist, swap behind `/plan`, verify downstream | 🟢 built, awaiting PR | — | Same worktree. Migration `20260606000000_class_lesson_slot_topics.sql`; `build_plan_inputs` + `persist_chapter_plan` + `GeneratePlanResult.source` in planner/plan services; class-scope cache extended to ordered topic-set (**D-12**). Full suite 186 passed / 41 skipped (7 new DB-gated tests skip without Postgres). Bundled into ONE combined PR with Phase 1. |

**Next thing to do:** Open ONE combined PR (Phase 1 + 2) from worktree `agent-ace8f70793ef27265` → `staging`. After merge, watch BOTH Railway deploys; the migration applies automatically on deploy. Then mark both phases ✅ and close beads. Known pre-existing bug to track separately: `generated_lps/service._parse_grade_int` expects `'G<n>'` but `grades.code` is INT — see bead `dars-grade-int-parse`.

## Step 6 — Where to find supporting context
- Existing planners being fronted/fallen-back-to: `server/src/dars/breakdown/chapter_plan_service.py`, `lp_type_heuristics.py`.
- LLM wrapper (API-key backend, D-10): `server/src/dars/breakdown/llm_client.py` (`call_llm`, `AsyncAnthropic`, `ANTHROPIC_API_KEY`).
- Downstream dispatch (unchanged): `server/src/dars/generated_lps/` (`lp_assistant_client.py`, `service.py`, `batch_service.py`), `server/src/dars/generated_exams/`.
- Endpoint to wire behind: `server/src/dars/v2_api/router_class_actions.py` (`break_down_chapter`, `POST /csts/{cst_id}/chapters/{book_chapter_id}/plan`).
- Migrations dir (only place for `.sql`): `server/src/dars/migrations/`.
- Beads: `.beads/status.jsonl`. Memory: `/home/hataf/.claude/projects/-home-hataf-taleemabad-dars/memory/`. Graph: `graphify-out/GRAPH_REPORT.md`.
- Related frozen features: `syllabus-breakdown-and-teacher-chapter-plan` (D-9/D-16/D-56/D-57), `lp-slo-injection-and-linkage` (D-1 custom_prompt), `ncp-english-g1-seed` (recommended_lp_type seed).

## Step 7 — Things to ask the user before acting
- Production deployment (default no).
- Schema changes not in `02-data-model.md`.
- A new runtime production dependency (the Agents SDK is **dev-only** per D-10 — do not make it a prod dependency).
- Re-seeding.

## Step 8 — How to start a phase as a fresh agent
1. Read this onramp + the active phase file.
2. Open the phase bead in `.beads/status.jsonl` (`status: in_progress`).
3. `git fetch origin staging` and branch from `origin/staging` **inside a worktree** (another agent shares the main tree).
4. Implement features in numbered order (F-N.1, F-N.2, …); meet each Acceptance.
5. Update Step 5 Current State + close the bead in the SAME PR; PR targets `staging`.
6. After merge, watch both Railway deploys.

## Step 9 — Keep the plan files alive (HARD RULE)
- Land a feature → update Step 5 (same PR).
- New decision → add `D-N` to `01-decision-log.md` (never overwrite; supersede).
- Schema change → update `02-data-model.md` in the migration's PR.
- New term → add to `00-glossary.md`.
- D-9 carries an explicit verify-or-extend follow-up (multi-topic LP cache key) — if you extend the cache key, log it as a new D-N.
- Self-check before closing a bead: Current State current? phase doc specs not stale? new decisions/terms logged? data model matches schema? a fresh agent could resume correctly?
