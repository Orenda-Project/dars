# Onramp — Dynamic Chapter Planner

You are a Claude agent picking up an in-flight effort. This file is your single entry point.
Reading it (and the files it lists) gives you the full context.

You will NOT execute any code, open beads, or write files until you have read everything this
file lists.

## Step 1 — Read these files, in this exact order
1. project CLAUDE.md (`dars/CLAUDE.md`)
2. `docs/features/dynamic-chapter-planner/README.md`
3. `docs/features/dynamic-chapter-planner/00-glossary.md`
4. `docs/features/dynamic-chapter-planner/01-decision-log.md`
5. `docs/features/dynamic-chapter-planner/02-data-model.md`
6. The phase file for the currently-active phase (see Step 5)
7. For context on the upstream that this builds on: the projector
   (`server/src/dars/breakdown/projector.py`), break-it-down
   (`server/src/dars/breakdown/chapter_plan_service.py:300-420`), and
   `mastery_service.submit_exam_results`.

## Step 2 — Document precedence
```
1. 01-decision-log.md         (D-N references are canonical)
2. 02-data-model.md           (schema is ground truth)
3. 00-glossary.md             (terminology)
4. phase docs                 (specs derived from above)
5. running code               (last; code may be stale)
```
If two docs disagree, this order wins. Code is lowest authority. Surface conflicts.

## Step 3 — Who you are in this conversation
- Implement phases sequentially. One bead per phase.
- PRs target **staging**. NEVER main (main deploys to prod on Railway).
- After every merge, watch BOTH deploys (server = `dars`, webapp = `truthful-renewal`) via
  the `railway` CLI (never the Railway MCP — CLAUDE.md rule 14).
- Treat the decision log as frozen.

## Step 4 — Conversational style (verbatim)
- Default mode: autonomous. Don't pause to confirm understanding.
- No pre-action narration ("I'll now do X"). Do X, report the result.
- One design question at a time via AskUserQuestion with 2–4 options + a Recommended.
- Use sub-agents for exploration (>3 search queries); synthesise yourself. Spawn
  build/implementation agents with `isolation: "worktree"`.
- Commit + push + open PR is ONE flow. PRs target staging.
- After merge, watch deploys (don't wait to be asked).
- Re-read a file before editing if you edited it earlier this session.

## Step 5 — Current state

| Phase | Status | PR(s) | Notes |
|-------|--------|-------|-------|
| 1 — Slot-mutation foundation | 🟡 built, awaiting PR merge | — | DONE on branch `feat/dynamic-chapter-planner-phase-1`: F-1.1 migration `20260612000000_dynamic_planner_slot_origin.sql` (origin/reteach_for_sub_slo_id/flex; sqlite-verified); F-1.2 `slot_mutation_service.py` (insert/remove/consume-flex, two-step large-offset renumber per D-12); F-1.3 `_assert_mutable` taught-lock; F-1.4 overflow read via `CstTimelineResponse.overflow_count` (D-13); F-1.5 `tests/test_slot_mutation_service.py` 13 tests green on sqlite. Suite: 273 passed / 60 skipped. Stays 🟡 until the PR squash-merges to staging. |
| 2 — Buffer-budgeted planner | ⬜ not started | — | flex/mandatory tagging, completion-target knob |
| 3 — Reteach trigger | ⬜ not started | — | mastery threshold → suggestion → confirm → consume-flex/insert → LP |

**Next thing to do:** Phase 1 code is complete on its branch; open the PR to staging, watch
both deploys on merge, then mark Phase 1 ✅ and close bead `feat-dynamic-chapter-planner-phase-1`.
After that: Phase 2 (F-2.1 …). New decisions logged this phase: D-12 (renumber/ids/DDL-split),
D-13 (overflow read seam).

Upstream dependency (FAs + breakdown holidays + exam periods on `syllabus_breakdowns`) is
**MERGED** (#136–#141). On-demand LP generation (`get_or_generate_lp`) is **MERGED** (#133).
Nothing blocks execution.

## Step 6 — Where to find supporting context
- Origin plan: `docs/plans/2026-06-12-dynamic-chapter-planner.md`
- Beads: `.beads/status.jsonl` (root bead `feat-dynamic-chapter-planner`)
- Memory: `~/.claude/projects/-home-hataf-taleemabad-dars/memory/project_dynamic_chapter_planner.md`
- Sibling subsystem: `docs/features/exam-periods-and-formative-assessments/` (the upstream)
- Graph: `graphify-out/GRAPH_REPORT.md`

## Step 7 — Things to ask the user before acting
- Production deployment (default no).
- Schema changes not in `02-data-model.md`.
- New external dependency.
- Re-seeding.
- `completion_target` home, at Phase 2 start (org default vs per-CST), if still ambiguous.

## Step 8 — How to start a phase as a fresh agent
1. Read this onramp + the active phase doc.
2. Open the phase bead `feat-dynamic-chapter-planner-phase-N` (append to status.jsonl, in_progress).
3. `git fetch origin staging && git checkout -b feat/dynamic-chapter-planner-phase-N origin/staging`.
4. Implement features in numbered order (F-N.1, F-N.2, …) to their Acceptance criteria.
5. Run tests (sqlite-runnable for mutation logic — no DATABASE_URL needed).
6. Commit → push → open PR to staging; update Step 5 in the same PR; on merge, watch both deploys, then close the bead.

## Step 9 — Keep the plan files alive (HARD RULE)
- Land a feature → update Step 5 (same PR).
- Complete a phase → mark ✅; close bead; append `## Notes from execution` to the phase doc if needed.
- New decision → add `D-N` to the decision log (rationale + when). Supersede, don't overwrite.
- Schema change → update `02-data-model.md` in the same PR as the migration.
- New term → add to `00-glossary.md`.
- Self-check before closing a bead: Step 5 current, no stale specs, decisions logged, data
  model matches schema, a fresh agent could identify the next step.
