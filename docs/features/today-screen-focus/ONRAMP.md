# Onramp — Today Screen Focus

You are a Claude agent picking up an in-flight effort. This file is your single
entry point. Reading it (and the files it lists) gives you the full context.

You will NOT execute code, open beads, or write files until you have read
everything this file lists.

## Step 1 — Read these files, in this exact order
1. project CLAUDE.md (`dars/CLAUDE.md`)
2. `docs/features/today-screen-focus/README.md`
3. `docs/features/today-screen-focus/01-decision-log.md`
4. `docs/features/today-screen-focus/03-phase-1-today-focus.md`

(No glossary or data-model doc — S feature, no schema change, no new concepts.)

## Step 2 — Document precedence
```
1. 01-decision-log.md         (D-N references are canonical)
2. phase docs                 (specs derived from above)
3. running code               (last; code may be stale)
```

## Step 3 — Who you are in this conversation
- One phase, one PR. One bead for the phase.
- PR targets **staging**. NEVER main.
- After merge, watch BOTH deploys (server changed in F-1.2, webapp changed in F-1.1/1.3/1.4).
- Treat the decision log as frozen.

## Step 4 — Conversational style (verbatim)
- Default mode: autonomous. Don't pause to confirm understanding.
- No pre-action narration ("I'll now do X").
- One design question at a time via AskUserQuestion with 2–4 options + a Recommended.
- Commit + push + open PR is ONE flow.
- After merge, watch deploys (don't wait to be asked).
- Re-read a file before editing if you edited it earlier this session.

## Step 5 — Current state

| Phase | Status | PR |
|-------|--------|----|
| Phase 1 — Today screen focus (F-1.1 … F-1.4) | 🟡 built; PR open | (pending) |

**Next thing to do:** PR is open against staging. After merge, watch BOTH
Railway deploys (server changed in F-1.2, webapp in F-1.1/1.3/1.4), then mark
this phase ✅ and close the bead `feat-today-screen-focus-phase-1`.

**Built (all verified):** backend 300 passed/60 skipped; webapp tsc clean,
eslint 0 errors (3 pre-existing unrelated warnings), `npm run build` clean with
`/teacher-app/today` in the manifest.

## Step 6 — Where to find supporting context
- Today screen: `webapp/app/teacher-app/today/page.tsx` + `webapp/components/templates/today-template.tsx`
- Reusable bar idiom: `CoverageMeter` in `webapp/components/templates/class-today-tab.tsx`
- Coverage endpoint: `get_sub_slo_coverage` in `server/src/dars/v2_api/router_class_actions.py` (~line 227)
- FE API client + types: `webapp/lib/dars-api.ts` (`SubSLOCoverageEntry`, `progressApi.getSubSLOCoverage`)
- Beads: `.beads/status.jsonl`

## Step 7 — Things to ask the user before acting
- Production deployment (default no)
- Any schema change (there should be none — flag if one becomes necessary)

## Step 8 — How to start the phase as a fresh agent
1. Read this onramp + the phase doc.
2. Open the bead `feat-today-screen-focus-phase-1`.
3. Branch from staging: `git fetch origin staging && git checkout -b feat/today-screen-focus origin/staging`.
4. Implement F-1.1 … F-1.4 in numbered order.
5. Update Step 5 Current State; commit + push + open PR to staging; close the bead after staging is green.

## Step 9 — Keep the plan files alive (HARD RULE)
- Land the phase → mark ✅ in Step 5 in the same PR.
- New decision the plan didn't anticipate → add `D-N` to the decision log.
- Found a mistake in a plan file → fix it immediately.
- Self-check before closing the bead: Step 5 reflects reality; new decisions logged;
  a fresh agent reading this onramp would know what's done and what's next.
