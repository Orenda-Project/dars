# Onramp — Teacher-App LP View + Polling

You are a Claude agent picking up an in-flight effort. This file is your single entry point. Reading it (and the files it lists) gives you the full context.

You will NOT execute any code, open beads, or write files until you have read everything this file lists.

## Step 1 — Read these files, in this exact order
1. `dars/CLAUDE.md` (project operating manual)
2. `docs/features/teacher-app-lp-view-polling/README.md`
3. `docs/features/teacher-app-lp-view-polling/01-decision-log.md` ← load-bearing
4. `docs/features/teacher-app-lp-view-polling/03-phase-1-lp-view-page.md`

No glossary or data-model doc — this feature adds no domain concept and no schema change.

## Step 2 — Document precedence
```
1. 01-decision-log.md   (D-N references are canonical)
2. phase docs           (specs derived from above)
3. running code         (last; code may be stale)
```
If two docs disagree, this order wins. Code is lowest authority. Surface conflicts; don't silently pick a side.

## Step 3 — Who you are in this conversation
- Implement the single phase. One bead.
- PRs target `staging`. NEVER `main`.
- After merge, watch BOTH deploys (server + webapp) — though this phase touches webapp only, confirm the webapp deploy goes green on the merge commit.
- Treat the decision log as frozen.

## Step 4 — Conversational style (verbatim)
- Default mode: autonomous. Don't pause to confirm understanding.
- No pre-action narration ("I'll now do X").
- One design question at a time via AskUserQuestion with 2–4 options + a Recommended.
- Use sub-agents for exploration (>3 search queries); synthesise yourself.
- Commit + push + open PR is ONE flow — and only on explicit user go-ahead (push is hook-blocked otherwise).
- After merge, watch deploys (don't wait to be asked).
- Re-read a file before editing if you edited it earlier this session.

## Step 5 — Current state

| Phase | Status | PR | Notes |
|---|---|---|---|
| Phase 1 — LP view page + 5s polling | 🟡 Built, awaiting merge | — | F-1.1…F-1.6 implemented on `feat/teacher-app-lp-view-polling`. tsc + eslint clean, `next build` green (route `ƒ /teacher-app/lp/[slot_id]` registered). Bead `feat-teacher-app-lp-view-polling`. Will be ✅ after merge to staging (admin) + webapp deploy green. |

**Next thing to do:** Merge `feat/teacher-app-lp-view-polling` → `staging` with admin override, then watch the webapp Railway deploy (`truthful-renewal`) go green on the merge commit. Then mark this phase ✅ and close the bead.

**What was built:** Page `webapp/app/teacher-app/lp/[slot_id]/page.tsx` (auto-start on `not_generated`, 5s poll to READY/ERROR, ~10min ceiling + "Keep checking", ERROR→message+Retry, READY→`lp_content` via `dangerouslySetInnerHTML`). Class-page Generate action now navigates here (F-1.6, see phase doc Notes); inline `generateLPAndPoll`/`generatingSlotId` removed as dead code. Did NOT reuse `LPViewer` (stub, D-5).

## Step 6 — Where to find supporting context
- API client: `webapp/lib/dars-api.ts` (`slots.*`, `ClassLessonSlotDetail` type, `request()` wrapper)
- Slot-read backend (reference only, no change): `server/src/dars/v2_api/router_generation.py:190-251`
- Existing inline poll precedent: `webapp/app/teacher-app/classes/[cst_id]/page.tsx` (`generateLPAndPoll`, ~L641)
- Teacher-app shell/layout: `webapp/components/templates/teacher-app-shell.tsx`, `webapp/app/teacher-app/layout.tsx`
- Reusable pieces: `LpContextHeader`, `CoveredSLOs` molecules (NOT `LPViewer` — stub)
- Beads: `.beads/status.jsonl`
- Memory: `~/.claude/projects/-home-hataf-taleemabad-dars/memory/`
- Staging test org (NCP, G1 English has a real LP path): see memory `ref_staging_test_account_ncp.md`
- Staging URLs: backend `dars-staging.up.railway.app` · webapp `dars-fe-stage.up.railway.app`

## Step 7 — Things to ask the user before acting
- Production deployment (default no — staging only)
- Any backend/schema change (this phase should need none; if you think it does, stop and ask)
- New frontend dependency (default no — match the existing plain-fetch + setTimeout pattern; do NOT add SWR/react-query)

## Step 8 — How to start (fresh agent recipe)
1. Read this onramp + the files in Step 1.
2. Read the phase doc.
3. Open/confirm the bead `feat-teacher-app-lp-view-polling` (in_progress).
4. `git fetch origin staging && git worktree add <path> -b feat/teacher-app-lp-view-polling origin/staging` (always a worktree).
5. Implement F-1.1…F-1.6 in order; verify against the phase doc's Verification section on staging.
6. Update Step 5 here in the same PR; close the bead after merge + green deploy.

## Step 9 — Keep the plan files alive (HARD RULE)
- Land the feature → update Step 5 (same PR).
- New decision the plan didn't anticipate → add `D-N` to the decision log (rationale + when).
- Scope change mid-phase → revise the feature's Spec/Acceptance inline with a "Scope change YYYY-MM-DD" note; don't rewrite history.
- F-1.6 explicitly defers the slide-over-vs-navigate call to implementation → record the outcome under `## Notes from execution` in the phase doc.
- Self-check before closing the bead: Step 5 current, no stale specs, new decisions logged, a fresh agent could resume from this onramp alone.
