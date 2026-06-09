# Onramp — Chapter Planner in Dars

You are a Claude agent picking up an in-flight effort: merging the standalone
Chapter Planning Engine (`chapter-planner-app/`) into the dars backend. This file
is your single entry point.

You will NOT execute code, open beads, or write files until you have read
everything this file lists.

## Step 1 — Read these files, in this exact order
1. project CLAUDE.md (`dars/CLAUDE.md`)
2. docs/features/chapter-planner-in-dars/README.md
3. docs/features/chapter-planner-in-dars/01-decision-log.md  ← load-bearing
4. docs/features/chapter-planner-in-dars/02-data-model.md    ← slot↔topic, no migration
5. docs/features/chapter-planner-in-dars/00-glossary.md
6. The phase file for the active phase (see Step 5)
7. docs/features/chapter-planner-in-dars/05-reference-planner-contract.md

## Step 2 — Document precedence
```
1. 01-decision-log.md         (D-N references are canonical)
2. 02-data-model.md           (slot↔topic ground truth)
3. 00-glossary.md             (terminology)
4. phase docs                 (specs derived from above)
5. running code               (last; code may be stale)
```
Code is lowest authority. Surface conflicts; don't silently pick a side.

## Step 3 — Who you are in this conversation
- Implement phases sequentially. One bead per phase.
- PRs target `staging`. NEVER main.
- After every merge, watch BOTH deploys (server `dars` + webapp `truthful-renewal`
  in the Railway `dars` project — webapp only matters if you touched it; this
  feature is backend-only, so server is the one to watch).
- Treat the decision log as frozen.

## Step 4 — Conversational style (verbatim)
- Default mode: autonomous. Don't pause to confirm understanding.
- No pre-action narration ("I'll now do X").
- One design question at a time via AskUserQuestion with 2–4 options + a Recommended.
- Use sub-agents for exploration (>3 search queries); synthesise yourself.
- Spawn build/implementation sub-agents with isolation: "worktree".
- Commit + push + open PR is ONE flow.
- After merge, watch deploys (don't wait to be asked).
- Re-read a file before editing if you edited it earlier this session.

## Step 5 — Current state
| Phase | Status | PR | Bead |
|---|---|---|---|
| 1 — Port planner core + agent-sdk backend + `/plan` endpoint | ✅ done | #128 | feat-chapter-planner-in-dars-phase-1-port |
| 2 — Wire into `generate_chapter_plan`; delete `chapter-planner-app/` | ✅ done | _PR pending — stacks on #128_ | feat-chapter-planner-in-dars-phase-2-wire |

**Next thing to do:** feature complete. Land Phase 2 after #128 merges, then close the feature beads.

**Phase 1 landed:** planner core in `server/src/dars/breakdown/planner_models.py`, `planner_prompts.py`, `planner_llm.py`, `planner.py`; authenticated `POST /api/v2/plan` in `server/src/dars/v2_api/router_planner.py` (X-API-Key / X-Admin-Session via `get_current_org`); tests in `server/tests/test_planner.py` (29 tests, stub LLM, full suite green). No DB write (D-6), no schema/migration.

## Step 6 — Where to find supporting context
- Standalone app being absorbed: `chapter-planner-app/` (planner.py, planner_llm.py, models.py, prompts.py, config.py — the source of the port).
- Existing agent-sdk usage to mirror: `server/src/dars/v2_api/book_import_service.py`.
- The seam to replace in Phase 2: `server/src/dars/breakdown/chapter_plan_service.py::generate_chapter_plan` (the placeholder).
- Break-it-down caller: `server/src/dars/v2_api/router_class_actions.py`.
- Slot tables: `class_lesson_slots` + `class_lesson_slot_topics` (migrations `20260517`, `20260605`, `20260606`).
- Beads: `.beads/status.jsonl`. Memory: `~/.claude/projects/-home-hataf-taleemabad-dars/memory/`.

## Step 7 — Things to ask the user before acting
- Production deployment (default no)
- Any schema change (there should be NONE — D-9 uses existing tables)
- A new external dependency beyond `claude-agent-sdk` (already in the server)
- Re-seeding

## Step 8 — How to start a phase as a fresh agent
1. Read this onramp + the active phase file.
2. Open the phase's bead in `.beads/status.jsonl` (status in_progress).
3. `git fetch origin staging && git checkout -b feat/chapter-planner-in-dars-phase-N-... origin/staging`.
4. Implement features in numbered order (F-N.1, F-N.2, …); acceptance per phase doc.
5. Run `uv run pytest` (cd server) green.
6. Update Step 5 here in the SAME PR; commit → push → open PR to staging; watch the server deploy.

## Step 9 — Keep the plan files alive (HARD RULE)
- Land a feature → update Step 5 (same PR).
- Complete a phase → mark ✅; close bead; append `## Notes from execution` to the phase doc if anything diverged.
- New decision the plan didn't anticipate → add D-N to 01-decision-log.md.
- Supersede a decision → amend old ("Superseded by D-N on YYYY-MM-DD"), add new. Both stay.
- This feature should touch NO migration. If you think you need one, STOP and ask — it contradicts D-9 / 02-data-model.md.
- Self-check before closing a bead: Step 5 current, phase doc specs not stale, new decisions logged, a fresh agent could resume from this onramp.
