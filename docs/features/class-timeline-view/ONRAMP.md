# Onramp — Class Timeline View

You are a Claude agent picking up an in-flight effort. This file is your single
entry point. Reading it (and the files it lists) gives you the full context.

You will NOT execute any code, open beads, or write files until you have read
everything this file lists.

## Step 1 — Read these files, in this exact order
1. project CLAUDE.md (`/home/hataf/taleemabad/dars/CLAUDE.md`)
2. `docs/features/class-timeline-view/README.md`
3. `docs/features/class-timeline-view/00-glossary.md`
4. `docs/features/class-timeline-view/01-decision-log.md`
5. The phase file for the currently-active phase (see Step 5)
6. For Phase 1: `server/src/dars/breakdown/projector.py`, `server/src/dars/v2_api/router_class_actions.py`, `server/src/dars/v2_api/schemas_class_actions.py`
7. For Phase 2: `webapp/CLAUDE.md` + `webapp/AGENTS.md` (Next.js here has breaking changes — read `node_modules/next/dist/docs/` before app code), `webapp/app/teacher-app/classes/[cst_id]/page.tsx`, the existing `class-lessons-tab.tsx` / `class-assessments-tab.tsx`

## Step 2 — Document precedence
```
1. 01-decision-log.md   (D-N references are canonical)
2. 00-glossary.md       (terminology)
3. phase docs           (specs derived from above)
4. running code         (last; code may be stale)
```
Code is lowest authority. Surface conflicts; don't silently pick a side.

## Step 3 — Who you are in this conversation
- Implement phases sequentially. One bead per phase.
- PRs target `staging`. NEVER `main`.
- After every merge, watch BOTH deploys (server + webapp — webapp is Railway, not Vercel).
- Treat the decision log as frozen.

## Step 4 — Conversational style (verbatim)
- Default mode: autonomous. Don't pause to confirm understanding.
- No pre-action narration ("I'll now do X").
- One design question at a time via AskUserQuestion with 2–4 options + a Recommended.
- Use sub-agents for exploration (>3 search queries); synthesise yourself.
- Commit + push + open PR is ONE flow.
- After merge, watch deploys (don't wait to be asked).
- Re-read a file before editing if you edited it earlier this session.

## Step 5 — Current state

| Phase | Status | PR |
|-------|--------|----|
| Phase 1 — Merged timeline endpoint (`GET /csts/{id}/timeline`) | 🟡 in PR | (pending) |
| Phase 2 — Unified timeline tab (frontend) | ⬜ not started | — |

**Next thing to do:** Phase 1 endpoint is implemented (F-1.1 route + F-1.2 schemas + F-1.3 tests) on branch `feat/class-timeline-view-phase-1-endpoint`; PR open against `staging`. After merge + green deploy, mark Phase 1 ✅ and start Phase 2 (`04-phase-2-timeline-tab.md`).

## Step 6 — Where to find supporting context
- Beads: `.beads/status.jsonl`
- Memory: `/home/hataf/.claude/projects/-home-hataf-taleemabad-dars/memory/`
- Graph report: `graphify-out/GRAPH_REPORT.md`
- Projector (reused verbatim, D-5): `server/src/dars/breakdown/projector.py` → `project_cst_schedule`
- Existing per-kind list endpoints to copy SQL from: `router_class_actions.py:283-399`
- Staging URLs: backend `dars-staging.up.railway.app` · webapp `dars-fe-stage.up.railway.app`

## Step 7 — Things to ask the user before acting
- Production deployment (default no)
- Any schema change (this feature is no-schema by D-11 — if one becomes necessary, ask + log a decision first)
- New external dependency
- Re-seeding

## Step 8 — How to start a phase as a fresh agent
1. Read this onramp + the active phase file.
2. Open the phase bead in `.beads/status.jsonl` (`status: in_progress`).
3. `git fetch origin staging && git checkout -b feat/class-timeline-view-phase-N-<slug> origin/staging`.
4. Implement features in numbered order (F-N.1, F-N.2 …) to their acceptance criteria.
5. Update Step 5 Current state in THIS file in the same PR.
6. Commit → push → open PR targeting `staging`; after merge, watch both deploys; close the bead.

## Step 9 — Keep the plan files alive (HARD RULE)
- Land a feature → update Step 5 (same PR).
- New decision the plan didn't anticipate → add `D-N` to `01-decision-log.md`.
- New term → add to `00-glossary.md`.
- Supersede a decision → mark old "Superseded by D-N on YYYY-MM-DD"; both stay.
- Self-check before closing a bead: Current State accurate · no stale specs · new decisions logged · a fresh agent could resume from this onramp.
