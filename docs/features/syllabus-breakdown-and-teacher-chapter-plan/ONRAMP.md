# Onramp — for the syllabus-breakdown-and-teacher-chapter-plan work

You are a Claude agent picking up an in-flight effort. This file is your single entry point.

You will NOT execute any code, open beads, or write files until you have read everything this file lists.

## Step 1 — Read these files, in this exact order
1. `dars/CLAUDE.md` — project rules (critical: 1–15; autonomous mode, no narration, never push main, re-read before edit).
2. `docs/features/syllabus-breakdown-and-teacher-chapter-plan/README.md`
3. `docs/features/syllabus-breakdown-and-teacher-chapter-plan/00-glossary.md`
4. `docs/features/syllabus-breakdown-and-teacher-chapter-plan/01-decision-log.md` — D-1…D-15 frozen.
5. `docs/features/syllabus-breakdown-and-teacher-chapter-plan/02-data-model.md` — drop old tables, create syllabus_*.
6. The active phase file (see Step 5).
7. The shipped `docs/features/chapter-breakdown-and-plan/` (this re-architects it; D-13).

## Step 2 — Document precedence
```
1. 01-decision-log.md   (D-N references are canonical)
2. 02-data-model.md     (schema is ground truth)
3. 00-glossary.md       (terminology)
4. phase docs           (specs derived from above)
5. running code         (last; code may be stale)
```
Surface conflicts; don't silently pick a side.

## Step 3 — Who you are in this conversation
- Implement phases sequentially. One bead per phase.
- PRs target `staging`. NEVER `main`. NEVER prod.
- After every merge, watch BOTH Railway deploys (server `dars` 602e331e…; webapp `truthful-renewal` 3d749686…) via `railway` CLI (MCP auth is flaky — CLI works: `railway deployment list`).
- Decisions D-1…D-15 are frozen. To revise: ask user, then "Superseded by D-N+1".

## Step 4 — Conversational style (verbatim)
- Default mode: autonomous. Don't pause to confirm understanding.
- No pre-action narration. Do it, report the result.
- One design question at a time via AskUserQuestion with 2–4 options + a Recommended.
- Sub-agents for exploration (>3 searches); synthesise yourself.
- Commit + push + open PR is ONE flow. User merges (or authorizes admin merge).
- After merge, watch deploys without being asked.
- Re-read a file before editing if you edited it earlier this session.
- "gg" when something works; "chammaar" when it breaks.

## Step 5 — Current state
**As of 2026-06-02 — plan approved, Phase 1 starting.**

| Phase | Scope | Status |
|---|---|---|
| Plan + onramp | folder, decision log, data model | ✅ |
| Phase 1 — rename (copy/docs) | F1.1 UI copy · F1.2 API docstrings · F1.3 docs/memory | ✅ code complete; PR open |
| Phase 2 — demolition + table rename | F2.1 salvage planners · F2.2 del realize · F2.3 del fork · F2.4 del slot UI/API · F2.5 migration+reseed · F2.6 global-only | ✅ code complete; PR open. Re-seed of 2 globals pending migration deploy. |
| Phase 3 — teacher Chapter Plan | F3.1 syllabus-by-today · F3.2 slot-count · F3.3 generate · F3.4 UI · F3.5 periods | ⬜ |

**Next thing to do:** open bead `feat-syllabus-breakdown-phase-1-rename`, branch from staging, do the user-facing rename (Phase 1 is copy/docs only — the code+table rename is in Phase 2 where the migration lives).

## Step 6 — Where to find supporting context
- Architecture map of the OLD system: see the Explore-agent findings in this feature's conversation; key files: `router_breakdown.py`, `fork_service.py`, `realize_service.py`, `auto_build_service.py`, `projector.py`, `chapter_calendar.py`.
- Staging DB (Railway Postgres) connection string is in the conversation / `creds/dars/dars.txt` (outside the repo). 2 global breakdowns currently exist (Dars + NCP G1 Eng) — Phase 2 drops + re-seeds them into syllabus_* tables.
- Beads: `.beads/status.jsonl`. Graph: `graphify-out/`.

## Step 7 — Things to ask the user before acting
- Production deploy (default no).
- Schema changes beyond `02-data-model.md`.
- Re-seeding shape changes.
- Anything that would touch the data bank (SLOs/books/topics) — D-11 says don't.

## Step 8 — How to start a phase as a fresh agent
1. Read this onramp end to end.
2. Read the active phase file.
3. Open the phase bead in `.beads/status.jsonl` (in_progress).
4. `git fetch origin staging && git checkout -b feat/syllabus-breakdown-phase-N origin/staging`.
5. Implement features in numbered order; acceptance per phase doc.
6. Update Step 5 in the same PR; commit+push+PR to staging; watch both deploys; close bead.

## Step 9 — Keep the plan files alive (HARD RULE)
- Land a feature → update Step 5 (same PR).
- New decision → add D-N to `01-decision-log.md`.
- Schema change → update `02-data-model.md` with the migration.
- New term → add to `00-glossary.md`.
- Self-check before closing a bead: Current State current? Decisions logged? Data model matches schema? A fresh agent would know what to do next?
