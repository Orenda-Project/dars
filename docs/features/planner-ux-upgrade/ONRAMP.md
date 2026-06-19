# Onramp — Planner UX Upgrade

You are a Claude agent picking up an in-flight effort. This file is your single
entry point. Reading it (and the files it lists) gives you the full context.

You will NOT execute any code, open beads, or write files until you have read
everything this file lists.

## Step 1 — Read these files, in this exact order
1. project CLAUDE.md (`/home/hataf/taleemabad/dars/CLAUDE.md`)
2. `webapp/CLAUDE.md` + `webapp/AGENTS.md` (Next.js 16 here is NOT your training data — read `node_modules/next/dist/docs/` before writing Next code)
3. `docs/features/planner-ux-upgrade/README.md`
4. `docs/features/planner-ux-upgrade/00-glossary.md`
5. `docs/features/planner-ux-upgrade/01-decision-log.md` ← **load-bearing**
6. The phase file for the currently-active phase (see Step 5)
7. Inherited constraints: `docs/features/teacher-adjustable-syllabus/01-decision-log.md` (D-1/D-6/D-7/D-10/D-11/D-13) and its `02-data-model.md` (schema ground truth — this feature adds nothing to it)

There is no `02-data-model.md` in this folder — **no schema change** (D-2).

## Step 2 — Document precedence
```
1. 01-decision-log.md         (D-N references are canonical)
2. 00-glossary.md             (terminology)
3. phase docs                 (specs derived from above)
4. running code               (last; code may be stale)
```
Inherited decisions from `teacher-adjustable-syllabus` are NOT superseded; this
feature's D-N labels are its own and renumber from D-1.

## Step 3 — Who you are in this conversation
- Implement phases sequentially. One bead per phase.
- PRs target **staging**. NEVER main.
- After every merge, watch BOTH Railway deploys (server + webapp) — though this
  feature is webapp-only, confirm webapp deploy is SUCCESS before closing.
- Treat the decision log as frozen.

## Step 4 — Conversational style (verbatim)
- Default mode: autonomous. Don't pause to confirm understanding.
- No pre-action narration ("I'll now do X"). Do it, then report.
- One design question at a time via AskUserQuestion with 2–4 options + a Recommended.
- Use sub-agents for exploration (>3 search queries); synthesise yourself.
- Use sub-agents (worktree isolation) for self-contained builds >4 files.
- Commit + push + open PR is ONE flow — only on explicit user request (push is hook-blocked; PRs target staging).
- After merge, watch deploys (don't wait to be asked).
- Re-read a file before editing if you edited it earlier this session.

## Step 5 — Current state

| Phase | Status | PR | Notes |
|-------|--------|----|-------|
| Plan (folder + decision log) | ✅ | — | Frozen 2026-06-19 |
| **Phase 1 — Holidays on planner + client-side warnings** | 🟡 in flight | — | F1.1 ✅ F1.2 ✅ F1.3 ✅ built locally (tsc clean); 🟡 until PR merges |
| **Phase 2 — Anchor auto-pack + drag-to-reorder** | 🟡 in flight | — | F2.1 ✅ F2.2 ✅ F2.3 ✅ F2.4 ✅ built locally (tsc 0 errors, lint clean on changed files); 🟡 until PR merges. `@dnd-kit` added (core ^6.3.1 / sortable ^10.0.0 / utilities ^3.2.2). O-1 resolved → D-9. |

**Next thing to do:** Both phases built locally on
`feat/planner-ux-upgrade-phase-1`; awaiting one PR → staging → `--admin` merge →
deploy-watch. Phase 2 added: `webapp/lib/planner-pack.ts`
(`autoPack`/`reflowFrom` — pure, holiday-aware teaching-day model, D-6 lock,
D-9 sizing); page-level `runPathRepack` (F2.4 sequential PATCH runner, D-7),
`handleAutoPack` (F2.1), downstream-only re-flow in `handleSetDates` (F2.3) and
`handleReorderAndReflow` (F2.2); template anchor-date "Auto-pack chapters" panel
+ `@dnd-kit` sortable rows with drag handle (▲▼ kept as a11y fallback).

**Environment facts gathered at build start (2026-06-19):**
- webapp: Next 16.2.1, React 19.2.4. No `@dnd-kit`, no date lib, no test script.
  Phase 1 needs none of these (vanilla date math; rendering only).
- Holidays already fetched on the class page (`holidaysApi.getCSTHolidays` →
  `{ items: Holiday[]; effective_dates: ISODate[] }`), used only on the
  Timetable tab today. F1.1 lifts it into the Syllabus tab.
- Server overlap algorithm to mirror: `compute_range_warnings` in
  `server/src/dars/breakdown/chapter_calendar.py` (overlap when
  `cur.start <= prev.end` for position-consecutive dated chapters).
- `slot_count` per chapter = holiday-aware teaching-period capacity, recomputed
  server-side on every read (`chapter_slot_count` in `class_chapter_service.py`).

## Step 6 — Where to find supporting context
- Syllabus tab template: `webapp/components/templates/class-syllabus-tab.tsx`
- Class page (owns fetches + callbacks): `webapp/app/teacher-app/classes/[cst_id]/page.tsx`
- API client: `webapp/lib/dars-api.ts` (`holidays`, `slots` exports)
- Inherited decisions: `docs/features/teacher-adjustable-syllabus/`
- Holiday model + dynamic planner: `docs/features/dynamic-chapter-planner/`
- Work tracking: `.beads/status.jsonl`
- Graph report: `graphify-out/GRAPH_REPORT.md`

## Step 7 — Things to ask the user before acting
- Production deployment (default no)
- Any schema change (this feature has none — D-2; a change means rethinking scope)
- Adding `@dnd-kit` is pre-approved by D-8 for Phase 2; no need to ask, just add it then.
- O-1 (default span for an undated chapter during auto-pack) — ask at F2.1.

## Step 8 — How to start a phase as a fresh agent
1. Read this onramp end to end + the active phase doc.
2. Cross-check `.beads/status.jsonl` against Step 5; the bead wins.
3. Open the phase bead `feat-planner-ux-upgrade-phase-N-<slug>` (`in_progress`).
4. `git fetch origin staging && git checkout -b feat/planner-ux-upgrade-phase-N-<slug> origin/staging` in a worktree.
5. Implement features in numbered order (F-N.1, F-N.2, …) to each acceptance bar.
6. Update this onramp's Step 5 in the SAME PR; close the bead when staging is green.

## Step 9 — Keep the plan files alive (HARD RULE)
- Land a feature on staging → update Step 5 (same PR).
- Make a decision the plan didn't anticipate → add `D-N` to `01-decision-log.md`
  (resolve O-1 as a new D-N when auto-pack is built).
- Introduce a new term → add to `00-glossary.md`.
- Find a mistake in any plan file → fix immediately.
- Self-check before closing a bead: Step 5 current, no stale specs, new
  decisions logged, a fresh agent could resume from this file alone.
