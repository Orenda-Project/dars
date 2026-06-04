# Onramp — Chapter Planning Engine (v2 standalone)

You are a Claude agent picking up an in-flight effort. This file is your single entry point.
Reading it (and the files it lists) gives you the full context. Do NOT execute code, open beads, or
write files until you've read everything this file lists.

## Step 1 — Read these, in order
1. project CLAUDE.md (`dars/CLAUDE.md`)
2. `docs/features/chapter-planner-engine/README.md`
3. `docs/features/chapter-planner-engine/00-glossary.md`
4. `docs/features/chapter-planner-engine/01-decision-log.md`  ← load-bearing
5. `docs/features/chapter-planner-engine/02-data-model.md`
6. The phase doc for the active phase (see Step 5)
7. `docs/features/chapter-planner-engine/06-reference-ug-lp-input.md` (the output target)

## Step 2 — Document precedence
1. 01-decision-log.md (D-N canonical) · 2. 02-data-model.md (contracts) · 3. 00-glossary.md ·
4. phase docs · 5. running code (lowest). Surface conflicts; don't silently pick a side.

## Step 3 — Who you are
- Implement phases sequentially. One bead per phase.
- This is a STANDALONE app at `dars/chapter-planner-app/`. It is NOT imported by `dars/server/`.
- PRs target `staging`. NEVER main.
- After every merge, watch the relevant deploy (CPE is standalone — it has no Railway service yet;
  if/when one is added, watch it; otherwise this is a no-op for now).

## Step 4 — Conversational style
- Default mode: autonomous. Don't pause to confirm understanding.
- No pre-action narration ("I'll now do X"). Do it, then report.
- One design question at a time via AskUserQuestion with 2–4 options + a Recommended.
- Use sub-agents for exploration (>3 search queries); synthesise yourself.
- Commit + push + open PR is ONE flow.
- Re-read a file before editing if you edited it earlier this session.

## Step 5 — Current state
| Phase | Status | PR |
|-------|--------|----|
| Plan + onramp | ✅ | (branch `feat/chapter-planner-engine-v2`) |
| P1 — scaffold + stub `/plan` + playground | ✅ | #115 |
| P2 — LLM planner core | ✅ | (this branch) |
| P3 — data-backed frontend (reshaped, D-10) | ✅ | (this branch) |

**Reshaped (D-10):** Phase 3 became a **data-backed frontend** instead of the generic iteration
harness (`05-phase-3-iteration-harness.md` is superseded by D-10). Done: read-only `db.py` over
staging (`DARS_STAGING_DATABASE_URL`, SELECT-only), `GET /books` · `/books/{id}/chapters` ·
`/books/{id}/chapters/{cid}/plan-input` (per-topic targets = topic's sub-SLOs), and a real UI in
`static/index.html` (book → chapter → review topics/sub-SLOs → Plan → rendered units, raw-JSON
toggle). No persistence. Verified: boots, `/books` returns the 2 real Eng books, 10 chapters load,
live `/plan` on "The Clever Crow" → valid 5-unit plan; 16 tests still green. asyncpg added.

**Run it:** `cd chapter-planner-app && .venv-test/bin/python -m uvicorn main:app --port 4100`,
open `http://localhost:4100/`.

**Possible next:** the UG_LP adapter (PlanUnit → /generate-lp request) for end-to-end LP generation,
or production re-integration into dars (D-9, separate feature).

P2 done & verified: `planner_llm.py` (AgentSdkPlannerLLM, D-13 lessons), `prompts.py`,
`planner.py` (parse + PlanValidator D-8 a–e, fail-loud per D-2), `/plan` wired (502 LLM / 422
invalid). 16 unit tests green (fake LLM). **Live acceptance:** "The Clever Crow" / 5 periods → 5
units, mixed lp_types (reading/comprehension_qa/grammar/revision), split a topic, all 6 SLOs
covered, validator clean. The parser strips fences + prose preamble (the bug that broke the in-dars
planner — see PLANNER_REPORT.md). claude-agent-sdk + dev deps (pytest/httpx) added.

## Step 6 — Supporting context
- UG_LP reference shape: `06-reference-ug-lp-input.md` (don't re-read UG_LP source unless it changed).
- The path CPE will eventually replace (D-9): dars `docs/features/intelligent-chapter-planner/`.
- Beads: `.beads/status.jsonl`. Memory: `~/.claude/projects/-home-hataf-taleemabad-dars/memory/`.

## Step 7 — Ask the user before
- Production deployment (default no — v2 is standalone/dev).
- Any change to a frozen decision (needs OK + a "Superseded by" entry).
- A new external dependency beyond `claude-agent-sdk` + the FastAPI stack.
- Wiring CPE into the dars backend (that's D-9, a future feature — don't start it in v2).

## Step 8 — How to start a phase as a fresh agent
1. Read this onramp + the active phase doc.
2. Open the phase bead in `.beads/status.jsonl` (`status: in_progress`).
3. `git fetch origin staging && git checkout -b feat/cpe-phase-N-<slug> origin/staging`.
4. Implement features in numbered order; acceptance criteria in the phase doc.
5. Update Step 5 Current state in THIS file in the same PR.
6. PR → staging; on merge mark phase ✅, close bead, open next phase's bead.

## Step 9 — Keep the plan alive (HARD RULE)
- Land a feature → update Step 5 (same PR).
- New decision → add `D-N` to 01-decision-log.md (don't overwrite; supersede).
- New term → 00-glossary.md. Contract change → 02-data-model.md.
- Self-check before closing a bead: Current state accurate? new decisions logged? a fresh agent
  would know what's next? If any fails, fix before closing.
