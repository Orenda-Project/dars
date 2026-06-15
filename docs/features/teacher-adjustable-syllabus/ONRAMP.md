# Onramp — teacher-adjustable-syllabus

You are a Claude agent picking up this effort. Single entry point.

You will NOT execute code, open beads, or write files until you've read what this lists.

## Step 1 — Read in this order
1. `dars/CLAUDE.md` — project rules (1–15).
2. `docs/features/teacher-adjustable-syllabus/README.md` — scope (deliberately narrow).
3. `docs/features/teacher-adjustable-syllabus/00-glossary.md`
4. `docs/features/teacher-adjustable-syllabus/01-decision-log.md` — D-1…D-8 frozen.
5. `docs/features/teacher-adjustable-syllabus/02-data-model.md` — `class_chapters`.
6. The active phase file: `05-phase-3-revival.md` (Step 5). The decision log's **Revival** section (D-9…D-12) is the load-bearing read.

## Step 2 — Document precedence
```
1. 01-decision-log.md   (D-N canonical)
2. 02-data-model.md     (schema ground truth)
3. 00-glossary.md       (terminology)
4. phase docs
5. running code
```

## Step 3 — Who you are
- **Phase 3 (Revival) ships as ONE PR** (backend + frontend together; small + coupled).
- **Own worktree, own branch (D-15):** worktree `.claude/worktrees/teacher-adjustable-syllabus-revival`, branch `feat/teacher-adjustable-syllabus-revival` off `staging`. Isolated from `lp-context-header` — do NOT touch its worktree/files. NEVER main/prod.
- **Baseline:** lift the removed backend from commit `91e1763` (#109); graft the UI onto today's expandable tab (D-12) — do NOT revert `class-syllabus-tab.tsx`.
- **⚠️ Before F3.4/F3.5:** check the `lp-context-header` collision (see `05-phase-3-revival.md` + D-15) — if its Chapter Page (`webapp/app/teacher-app/classes/[cst_id]/chapters/[position]/page.tsx`) is on staging, put the edit affordances there, not on the removed accordion.
- After merge, watch BOTH Railway deploys (server + webapp; webapp is Railway, not Vercel) via `mcp__Railway__list_deployments`.

## Step 4 — Conversational style
- Autonomous; no pre-action narration. One question at a time via AskUserQuestion. Sub-agents for big self-contained builds. Re-read a file before editing if edited earlier. "gg"/"chammaar".

## Step 5 — Current state
**As of 2026-06-15 — 🟡 Phase 3 (Revival) BUILT on `feat/teacher-adjustable-syllabus-revival`; awaiting PR merge.**

History: Phases 1+2 shipped 2026-06-03 (PR #109) → then the mutation layer was **removed**
and the tab made read-only by `teacher-readonly-syllabus` (#130/#131). The `class_chapters`
table, auto-seed, and `list_class_path` survive on staging; pick/set-dates/reorder/remove +
the editable UI do not. User reopened it 2026-06-15 (full re-date + pick + reorder + remove).

| Phase | Scope | Status |
|---|---|---|
| Plan (orig) | scope, decision log D-1…D-8, data model | ✅ |
| Phase 1 — backend (#109) | `class_chapters` + pick/date/reorder/remove/recommend | ✅ shipped, then ⛔ removed by #130/#131 |
| Phase 2 — teacher UI (#109) | recommendation → pick → date → reorder → break down | ✅ shipped, then ⛔ read-only-fied by #130/#131 |
| Plan (revival) | D-9…D-12 + `05-phase-3-revival.md` | ✅ |
| **Phase 3 — Revival** | restore mutation layer + editable UI on today's auto-seeded expandable tab | 🟡 **built; awaiting PR merge** — backend mutation layer (pick/set-dates/reorder/remove + `validate_reorder` + D-11 `remove_chapter`) + endpoints/schemas + dars-api client + explicit Edit-syllabus mode grafted on the accordion (D-13). 311 backend tests pass; tsc/lint/build clean. |

**What changed since #109 (must account for):** (1) **auto-seed** stays — class path is
pre-copied from the org breakdown; teacher edits on top (D-10). (2) dynamic-planner added
`origin`/`reteach_for_sub_slo_id`/`flex` to slot tables → `remove_chapter` must reject any
chapter with generated slots (D-11). (3) the syllabus tab is now expandable-to-LPs (#147) —
graft edits onto it, don't revert (D-12).

**Next thing to do:** open bead `feat-teacher-adjustable-syllabus-phase-3-revival`, branch
`feat/teacher-adjustable-syllabus-revival` from staging, implement F3.1→F3.5 in order
(lift backend from `91e1763`, modulo D-11), one PR → staging, watch both deploys.

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
