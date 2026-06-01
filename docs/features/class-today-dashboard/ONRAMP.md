# Class Today Dashboard — onramp

You are a Claude agent picking up an in-flight effort. This file is your single
entry point. Reading it (and the files it lists) gives you the full context.
Do NOT execute code, open beads, or write files until you have read everything
this file lists.

## Step 1 — Read these files, in this exact order
1. `dars/CLAUDE.md` and `webapp/CLAUDE.md`
2. `docs/features/class-today-dashboard/README.md`
3. `docs/features/class-today-dashboard/00-glossary.md`
4. `docs/features/class-today-dashboard/01-decision-log.md`
5. `docs/features/class-today-dashboard/03-phase-1-today-dashboard.md`

## Step 2 — Document precedence
1. 01-decision-log.md (D-N canonical) · 2. 00-glossary.md · 3. phase doc ·
4. running code (lowest). Surface conflicts; don't silently pick a side.

## Step 3 — Who you are
- One phase, one bead, one PR to `staging`. NEVER main.
- After merge, watch BOTH deploys (server unaffected here; webapp via Vercel).
- Decision log is frozen.

## Step 4 — Conversational style
- Autonomous. No pre-action narration. One design question at a time.
- Commit + push + open PR is one flow. Watch deploys after merge unprompted.
- Re-read a file before editing if you edited it earlier this session.

## Step 5 — Current state
| Phase | Status | PR |
|-------|--------|----|
| 1 — Today dashboard (default class view) | ✅ Closed | #92 (merged 2026-06-01) |

**Next thing to do:** Feature shipped to staging. Verify the Vercel webapp
deploy is green (dars-fe-stage.up.railway.app / Vercel).

## Step 6 — Supporting context
- Touched files: `webapp/app/teacher-app/classes/[cst_id]/page.tsx`,
  `webapp/components/templates/class-detail-template.tsx`, new
  `webapp/components/templates/class-today-tab.tsx`.
- API surface: `webapp/lib/dars-api.ts` (`today`, `slots`, `progress`).
- Beads: `.beads/status.jsonl`. Memory: per MEMORY.md.

## Step 7 — Ask before acting
- Production deploy (default no) · schema changes (none planned) · new dep.

## Step 8 — How to start as a fresh agent
Read this onramp → read the phase doc → open the phase bead → branch from
staging → implement F1.1..F1.3 in order → update Step 5 + close bead in the PR.

## Step 9 — Keep plan files alive (HARD RULE)
Log any unplanned decision as D-N. Update Step 5 in the same PR as the feature.
Append `## Notes from execution` to the phase doc for limitations/follow-ups.
