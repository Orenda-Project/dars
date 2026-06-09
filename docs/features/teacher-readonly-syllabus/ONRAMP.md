# Onramp — Teacher Read-Only Syllabus

You are a Claude agent picking up an in-flight effort: making the teacher app's
syllabus read-only (org-owned), with the teacher's only action being "generate
chapter plan." This file is your single entry point.

You will NOT execute code, open beads, or write files until you have read
everything this file lists.

## Step 1 — Read these files, in this exact order
1. project CLAUDE.md (`dars/CLAUDE.md`)
2. docs/features/teacher-readonly-syllabus/README.md
3. docs/features/teacher-readonly-syllabus/01-decision-log.md  ← load-bearing
4. docs/features/teacher-readonly-syllabus/02-data-model.md    ← auto-seed copy rule, no migration
5. docs/features/teacher-readonly-syllabus/00-glossary.md
6. The phase file for the active phase (see Step 5)

## Step 2 — Document precedence
```
1. 01-decision-log.md   (D-N canonical)
2. 02-data-model.md     (table/copy ground truth)
3. 00-glossary.md       (terminology)
4. phase docs           (specs derived from above)
5. running code         (last; may be stale)
```

## Step 3 — Who you are in this conversation
- Implement phases sequentially. One bead per phase.
- PRs target `staging`. NEVER main.
- After every merge, watch the relevant Railway deploy(s): Phase 1 → `dars` server;
  Phase 2 → webapp (`truthful-renewal` service in the `dars` Railway project, NOT Vercel).
- Treat the decision log as frozen.

## Step 4 — Conversational style (verbatim)
- Default mode: autonomous. Don't pause to confirm understanding.
- No pre-action narration.
- One design question at a time via AskUserQuestion (2–4 options + a Recommended).
- Sub-agents for exploration (>3 searches); synthesise yourself.
- Spawn build/implementation sub-agents with isolation: "worktree".
- Commit + push + open PR is ONE flow.
- After merge, watch deploys (don't wait to be asked).
- Re-read a file before editing if you edited it earlier this session.

## Step 5 — Current state
| Phase | Status | PR | Bead |
|---|---|---|---|
| 1 — Backend: auto-seed + read-only GET; delete 4 mutation endpoints | ✅ done | [PR #PENDING](https://github.com/Orenda-Project/dars/pulls) | feat-teacher-readonly-syllabus-phase-1-backend |
| 2 — Frontend: read-only syllabus tab, generate-only; delete mutation client fns | ⬜ not started | — | feat-teacher-readonly-syllabus-phase-2-frontend |

**Next thing to do:** execute Phase 2 (`04-phase-2-frontend-readonly.md`) — read-only syllabus tab + delete the webapp client fns that hit the now-removed mutation endpoints. It depends on (and stacks on) Phase 1.

## Step 6 — Where to find supporting context
- Backend seam: `server/src/dars/breakdown/class_chapter_service.py` (path logic + new auto-seed), `server/src/dars/v2_api/router_class_actions.py` (syllabus GET + the 4 endpoints to delete + break-it-down), `schemas_class_actions.py` (response shapes), `chapter_plan_service.py` (`resolve_cst_syllabus_context`, `chapter_slot_count` — keep).
- Org breakdown: `syllabus_breakdowns` + `syllabus_chapters` (migration `20260604000000`); `class_chapters` (migration `20260603100000`).
- Frontend: `webapp/components/templates/class-syllabus-tab.tsx`, `webapp/app/teacher-app/classes/[cst_id]/page.tsx`, `webapp/lib/dars-api.ts`.
- Tests touching the deleted surface: `server/tests/test_class_chapter_service.py`, `server/tests/test_syllabus_api.py`.
- Beads: `.beads/status.jsonl`. Memory: `~/.claude/projects/-home-hataf-taleemabad-dars/memory/`.

## Step 7 — Things to ask the user before acting
- Production deployment (default no).
- Any schema change (should be NONE — D-6). If you think you need one, STOP and ask.
- Wipe-and-reseed of legacy partial paths (plan says leave-and-log; don't change without asking).
- Re-seeding demo data.

## Step 8 — How to start a phase as a fresh agent
1. Read this onramp + the active phase file.
2. Bead is in `.beads/status.jsonl` (in_progress).
3. `git fetch origin staging && git checkout -b feat/teacher-readonly-syllabus-phase-N-... origin/staging` (Phase 2 may stack on Phase 1's branch if unmerged).
4. Implement features in order; acceptance per phase doc.
5. `cd server && uv run pytest` green (Phase 1) / typecheck+build (Phase 2).
6. Update Step 5 here in the SAME PR; commit → push → open PR to staging; watch the deploy.

## Step 9 — Keep the plan files alive (HARD RULE)
- Land a feature → update Step 5 (same PR).
- Complete a phase → mark ✅; close bead; append `## Notes from execution` if anything diverged.
- New decision → add D-N to 01-decision-log.md. Supersede → amend old + add new; both stay.
- This feature touches NO migration. If you think you need one, STOP — it contradicts D-6.
- Self-check before closing a bead: Step 5 current, phase specs not stale, decisions logged, a fresh agent could resume.
