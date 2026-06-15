# Onramp — LP Context Header

You are a Claude agent picking up an in-flight effort. This file is your single entry point. Reading it (and the files it lists) gives you the full context.

You will NOT execute code, open beads, or write files until you have read everything this file lists.

## Step 1 — Read these files, in this exact order
1. project CLAUDE.md (`dars/CLAUDE.md`) + `webapp/CLAUDE.md` + `webapp/AGENTS.md`
2. `docs/features/lp-context-header/README.md`
3. `docs/features/lp-context-header/00-glossary.md`
4. `docs/features/lp-context-header/01-decision-log.md`
5. `docs/features/lp-context-header/02-data-model.md`
6. The three phase docs: `03-phase-1-backend-context-fields.md`, `04-phase-2-shared-header-and-labels.md`, `05-phase-3-syllabus-chapter-page.md`

## Step 2 — Document precedence
```
1. 01-decision-log.md         (D-N references are canonical)
2. 02-data-model.md           (response shape is ground truth)
3. 00-glossary.md             (terminology)
4. phase docs                 (specs derived from above)
5. running code               (last; code may be stale)
```

## Step 3 — Who you are in this conversation
- **Single PR** (user decision 2026-06-15): all three phases ship on one branch / one PR. The phases are an ordering of *work*, not separate PRs.
- PR targets `staging`. NEVER main.
- After merge, watch BOTH deploys (server + webapp).
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

Single PR. Branch: `feature/lp-context-header`.

| Work | Status |
|---|---|
| Phase 1 — backend context fields (F-1.1 topic_title on /today, F-1.2 chapter on slot-detail) | ✅ (uncommitted on branch) |
| Phase 2 — `lpTypeLabel()` + `LpContextHeader` + apply at slide-over/today/class-today/timeline | ✅ (uncommitted on branch) |
| Phase 3 — syllabus chapter page + row→navigation | 🟡 in progress |

**Next thing to do:** finish Phase 3 (chapter page route + syllabus row→Link), typecheck/lint, then commit all three phases + open the single PR.

## Step 6 — Where to find supporting context
- Backend LP endpoints: `server/src/dars/v2_api/router_today_calendar.py`, `router_generation.py`, `router_class_actions.py`. `lp_type` enum: `server/src/dars/breakdown/planner_models.py` (`VALID_LP_TYPES`).
- Frontend LP sites: `webapp/lib/dars-api.ts` (types), `webapp/components/molecules/lp-viewer.tsx`, `webapp/components/templates/today-template.tsx`, `class-today-tab.tsx`, `class-syllabus-tab.tsx`. Existing badge pattern: `webapp/components/molecules/reteach-panel.tsx`.
- Syllabus page: `webapp/app/teacher-app/classes/[cst_id]/page.tsx` (`?tab=syllabus`).
- Beads: `.beads/status.jsonl`. Memory: session memory dir. Graph: `graphify-out/GRAPH_REPORT.md`.

## Step 7 — Things to ask the user before acting
- Production deployment (default no).
- Schema changes (this feature has none — D-1; if one becomes necessary, ask).
- New external dependency.
- Re-seeding (not needed here).

## Step 8 — How to start as a fresh agent
1. Read this onramp + the files in Step 1.
2. Cross-check `.beads/status.jsonl` for the bead (bead wins on status).
3. If branch `feature/lp-context-header` exists, check it out and continue; else branch from `origin/staging`.
4. Execute remaining phase work in order (1→2→3) on the single branch.
5. Update Step 5 status as work lands; open/refresh the PR when complete.

## Step 9 — Keep the plan files alive (HARD RULE)
- New decision → add `D-N` to `01-decision-log.md` (don't overwrite; supersede).
- New term → `00-glossary.md`.
- Scope change → revise the phase doc's Spec/Acceptance inline with a dated note.
- Response-shape change → `02-data-model.md`.
- Self-check before closing the bead: Step 5 reflects reality; phase docs have no stale specs; new decisions logged; a fresh agent could resume from this file alone.
