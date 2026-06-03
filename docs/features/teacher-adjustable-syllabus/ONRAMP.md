# Onramp — teacher-adjustable-syllabus

You are a Claude agent picking up this effort. Single entry point.

You will NOT execute code, open beads, or write files until you've read what this lists.

## Step 1 — Read in this order
1. `dars/CLAUDE.md` — project rules (1–15).
2. `docs/features/teacher-adjustable-syllabus/README.md` — scope (deliberately narrow).
3. `docs/features/teacher-adjustable-syllabus/00-glossary.md`
4. `docs/features/teacher-adjustable-syllabus/01-decision-log.md` — D-1…D-8 frozen.
5. `docs/features/teacher-adjustable-syllabus/02-data-model.md` — `class_chapters`.
6. The active phase file (Step 5).

## Step 2 — Document precedence
```
1. 01-decision-log.md   (D-N canonical)
2. 02-data-model.md     (schema ground truth)
3. 00-glossary.md       (terminology)
4. phase docs
5. running code
```

## Step 3 — Who you are
- **This feature ships as ONE PR** (both phases) per user instruction — not phase-per-PR.
- **Working in a git worktree** `.claude/worktrees/teacher-adjustable-syllabus` on branch `feat/teacher-adjustable-syllabus` (another agent works the main checkout on `intelligent-chapter-planner` — do NOT touch their files).
- PR targets `staging`. NEVER main/prod.
- After merge, watch BOTH Railway deploys (server `dars`, webapp `truthful-renewal`) via `railway deployment list -s <svc>` (MCP auth flaky; CLI works).

## Step 4 — Conversational style
- Autonomous; no pre-action narration. One question at a time via AskUserQuestion. Sub-agents for big self-contained builds. Re-read a file before editing if edited earlier. "gg"/"chammaar".

## Step 5 — Current state
**As of 2026-06-03 — ✅ CLOSED. Shipped PR #109, server+webapp green, class_chapters live.**

| Phase | Scope | Status |
|---|---|---|
| Plan | scope, decision log, data model | ✅ |
| Phase 1 — backend | `class_chapters` + pick/date/reorder/recommend + break-it-down date source | ✅ built; 176 non-DB tests pass |
| Phase 2 — teacher UI | recommendation prompt → pick → date → reorder → break down | ✅ built; tsc clean |
| → single PR | both phases together | ✅ open |

**Phase 1 detail:** migration `20260603100000_class_chapters.sql` (validated rolled-back); new `class_chapter_service.py` (list/pick/set-dates/reorder/remove/recommend + derived status + reorder-lock, 19 logic tests); reworked `GET /csts/{id}/syllabus` + 4 CRUD endpoints; `generate_chapter_plan` now reads dates from `class_chapters`.
**Phase 2 detail:** reworked `class-syllabus-tab.tsx` (empty→recommendation prompt + pick-any; non-empty→ordered path with date edit, status badge, reorder ▲▼ with lock, remove, break-it-down); page handlers set state from each mutation's returned response; fixed a Today-tab regression (removed `is_current`/`is_planned` refs).

**Next:** after PR merges + both Railway deploys green, mark ✅ Closed; move to Closed in docs/features/README.md; close bead.

## Step 6 — Context
- Staging DB (Railway Postgres) conn string in conversation / `creds/dars/dars.txt`.
- Reuses: `chapter_plan_service.generate_chapter_plan`, `chapter_slot_count`, `resolve_cst_syllabus_context`, `compute_teaching_days`. Endpoint home: `router_class_actions.py`. Teacher UI: `webapp/app/teacher-app/classes/[cst_id]/page.tsx` + `class-syllabus-tab.tsx`.
- Validate migrations against staging in a rolled-back transaction BEFORE merge (lesson from prior feature's FK-order crash).

## Step 7 — Ask the user before
- Production deploy (default no). Schema changes beyond `class_chapters`. Touching generation/assessment logic (that's `intelligent-chapter-planner`, D-8). Touching the data bank.

## Step 8 — Start recipe
Already in the worktree on the branch; bead `feat-teacher-adjustable-syllabus` open. Build phases in order, single PR.

## Step 9 — Keep plan alive
New decision → D-N in decision log. Schema change → update `02-data-model.md` + migration. Update Step 5 in the PR. Self-check before closing the bead.
