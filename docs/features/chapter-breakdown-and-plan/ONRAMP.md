# Onramp — for the chapter-breakdown-and-plan work

You are a Claude agent picking up an in-flight effort. This file is your single entry point. Reading it (and the files it lists) gives you the full context.

You will NOT execute any code, open beads, or write files until you have read everything this file lists.

## Step 1 — Read these files, in this exact order
1. `dars/CLAUDE.md` — project rules (critical: rules 1–15; especially autonomous mode, no narration, never push to main, advisory-vs-blocking).
2. `docs/features/chapter-breakdown-and-plan/README.md` — index + what this feature does.
3. `docs/features/chapter-breakdown-and-plan/00-glossary.md` — feature-specific terms.
4. `docs/features/chapter-breakdown-and-plan/01-decision-log.md` — frozen decisions D-1…D-7.
5. `docs/features/chapter-breakdown-and-plan/02-data-model.md` — the two schema deltas.
6. The phase file for the active phase (see Step 5).
7. `docs/plans/2026-05-15-dars-v2-rebuild/02-data-model.md` Section 4 — base breakdown schema (cross-reference only; no changes there).

## Step 2 — Document precedence
```
1. 01-decision-log.md   (D-N references are canonical)
2. 02-data-model.md     (schema is ground truth)
3. 00-glossary.md       (terminology)
4. phase docs           (specs derived from above)
5. running code         (last; code may be stale)
```
If two docs disagree, this is the order. Surface conflicts; don't silently pick a side.

## Step 3 — Who you are in this conversation
- Implement phases sequentially. One bead per phase.
- PRs target `staging`. NEVER `main`. NEVER prod.
- After every merge, watch BOTH Railway deploys (server: `dars`; webapp). Phase isn't done until both show SUCCESS on the new commit.
- Decisions D-1…D-7 are frozen. To revise: ask the user, then "Superseded by D-N+1".

## Step 4 — Conversational style (verbatim)
- Default mode: autonomous. Don't pause to confirm understanding.
- No pre-action narration ("I'll now do X"). Do it, report the result.
- One design question at a time via AskUserQuestion with 2–4 options + a Recommended.
- Sub-agents for exploration (>3 search queries); synthesise yourself.
- Commit + push + open PR is ONE flow.
- After merge, watch deploys without being asked.
- Re-read a file before editing if you edited it earlier this session.
- Say "gg" when something works; "chammaar" when it breaks.

## Step 5 — Current state
**As of 2026-06-02 — Phase 1 implemented, PR open (first session).**

| Phase | Scope | Status |
|---|---|---|
| Plan + onramp | folder, decision log, data model | ✅ |
| Phase 1 — chapter date ranges | F1.1 schema · F1.2 derived days · F1.3 advisory validation · F1.4 dashboard editor | ✅ code complete; PR open to staging |
| Phase 2 — manual Chapter Plan | F2.1 page schema · F2.2 manual builder backend · F2.3 auto-build as seed · F2.4 dashboard editor | ⬜ not started |

**Phase 1 detail:** migration `20260602000000_breakdown_chapters_date_range.sql` (start_date/end_date nullable). New `server/src/dars/breakdown/chapter_calendar.py` (derived days + advisory warnings, reuses `projector.compute_teaching_days`; holiday source per D-8). Router `_hydrate_breakdown` now returns `derived_teaching_days` per chapter + `chapter_range_warnings`. Dashboard editor: per-chapter date pickers replace the day-count input (dates are primary, days derived/displayed); inline warning badges; chapters ordered by start_date. Tests: `tests/test_chapter_calendar.py` (7). Suite 152 passed.

**Next thing to do:** after Phase 1 PR merges and both Railway deploys are green, mark this phase ✅ merged, then start Phase 2 (open bead `feat-chapter-breakdown-and-plan-phase-2-chapter-plan`, branch from staging, F2.1→F2.4).

## Step 6 — Where to find supporting context
- Breakdown editor UI: `webapp/app/dashboard/breakdowns/[breakdown_id]/page.tsx`
- Breakdown endpoints: `server/src/dars/v2_api/router_breakdown.py`
- Breakdown schemas: `server/src/dars/v2_api/schemas_breakdown.py`
- Auto-build: `server/src/dars/breakdown/auto_build_service.py`
- Slot types constant: `webapp/lib/slot-types.ts` / `server/src/dars/v2_api/lp_types.py`
- Migrations: `server/src/dars/migrations/` (append-only)
- Beads: `.beads/status.jsonl`
- Graph: `graphify-out/GRAPH_REPORT.md`; use `graphify query "..."` for symbol lookup.

## Step 7 — Things to ask the user before acting
- Production deployment (default no — PRs target staging).
- Schema changes beyond the two deltas in `02-data-model.md`.
- Making date-range validation blocking instead of advisory (D-5 says advisory).
- Re-seeding demo data.

## Step 8 — How to start a phase as a fresh agent
1. Read this onramp end to end.
2. Read the active phase file.
3. Open the phase bead in `.beads/status.jsonl` (`status: in_progress`).
4. `git fetch origin staging && git checkout -b feat/chapter-breakdown-and-plan-phase-N origin/staging`.
5. Implement features in numbered order; acceptance criteria in the phase doc.
6. Update Step 5 here in the same PR; commit + push + open PR to staging; watch both deploys; close bead.

## Step 9 — Keep the plan files alive (HARD RULE)
- Land a feature → update Step 5 (same PR).
- New decision → add D-N to `01-decision-log.md`.
- Schema change → update `02-data-model.md` with the migration.
- New term → add to `00-glossary.md`.
- Found a stale spec → fix immediately.
- Self-check before closing a bead: Current State current? New decisions logged? Data model matches schema? A fresh agent would know what to do next?
