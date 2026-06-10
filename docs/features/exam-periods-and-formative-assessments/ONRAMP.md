# Onramp — Exam Periods & Formative Assessments

You are a Claude agent picking up an in-flight effort. This file is your single
entry point. Reading it (and the files it lists) gives you the full context.

You will NOT execute any code, open beads, or write files until you have read
everything this file lists.

## Step 1 — Read these files, in this exact order
1. project CLAUDE.md (`/home/hataf/taleemabad/dars/CLAUDE.md`)
2. `docs/features/exam-periods-and-formative-assessments/README.md`
3. `docs/features/exam-periods-and-formative-assessments/00-glossary.md`
4. `docs/features/exam-periods-and-formative-assessments/01-decision-log.md`
5. `docs/features/exam-periods-and-formative-assessments/02-data-model.md`
6. The phase file for the currently-active phase (see Step 5)
7. For Phase 3 only: skim `generated_exams/service.py` + the exam webhook router

## Step 2 — Document precedence
```
1. 01-decision-log.md   (D-N references are canonical)
2. 02-data-model.md     (schema is ground truth)
3. 00-glossary.md       (terminology)
4. phase docs           (specs derived from above)
5. running code         (last; code may be stale)
```
If two docs disagree, this order wins. Code is lowest authority.

## Step 3 — Who you are in this conversation
- Implement phases sequentially. One bead per phase.
- PRs target **staging**. NEVER main.
- After every merge, watch BOTH Railway deploys (`dars` backend + `truthful-renewal` webapp) per CLAUDE.md rule 14.
- Treat the decision log as frozen. To change a decision: ask, then add a new D-N marking the old "Superseded by D-N+1"; never overwrite.

## Step 4 — Conversational style (verbatim)
- Default mode: autonomous. Don't pause to confirm understanding.
- No pre-action narration ("I'll now do X"). Do it, then report.
- One design question at a time via AskUserQuestion with 2–4 options + a Recommended.
- Use sub-agents for exploration (>3 search queries); synthesise yourself.
- **Spawn build/implementation sub-agents with `isolation: "worktree"`.**
- Commit + push + open PR is ONE flow (target staging).
- After merge, watch deploys (don't wait to be asked).
- Re-read a file before editing if you edited it earlier this session.

## Step 5 — Current state

| Phase | Status | PR | Notes |
|-------|--------|----|----|
| Phase 1 — Exam Periods & Breakdown Holidays (`03-...`) | 🟡 In review | PR pending | Built F-1.1..F-1.6 on `feat/exam-periods-fa-phase-1`; route prefix is `/api/v2`; backend tests + webapp typecheck green; awaiting PR + deploy |
| Phase 2 — Planner emits FAs (`04-...`) | ⬜ Not started | — | |
| Phase 3 — FA → Exam Generator inputs (`05-...`) | ⬜ Not started | — | |

**Next thing to do:** open the Phase 1 PR against `staging`; after merge, watch both Railway deploys (the migration applies on the backend deploy). Then start Phase 2, F-2.1 (`PlanUnit.slot_type`).

**Implementation notes (Phase 1):** Two new decisions logged in `.beads/decisions.jsonl` — (1) the teacher-path breakdown resolution happens *internally* in `chapter_slot_count` / `project_cst_schedule` (no call-site signature change; projector uses a lazy import + inline `_resolve_published_breakdown_id` to dodge an import cycle); (2) no separate `exam_overlap` advisory — a chapter inside an exam/holiday window surfaces via the existing `zero_teaching_days` warning (D-4 left it optional). The endpoints live under `/api/v2/syllabus-breakdowns/{id}/exam-periods` and `/holidays` (NOT `/api/v1` — the phase doc's path strings were illustrative). `resolve_breakdown_holidays` in `chapter_calendar.py` is now unused but left defined (signature-stable future hook).

**Scope note (important):** Summative Assessments are **deferred** (D-16). Exam Periods are pure no-teaching blocked ranges only — no SA slots, no summative exam generation, no results capture in this feature. SAs are a follow-on the user will hand off separately. If you find yourself building SA slot creation here, stop — that's out of scope.

## Step 6 — Where to find supporting context
- Sibling/prior features: `docs/features/syllabus-breakdown-and-teacher-chapter-plan/` (D-1..D-16 prior) and `docs/features/intelligent-chapter-planner/` — the basis this builds on.
- Work tracking: `.beads/status.jsonl`.
- Graph: `graphify-out/GRAPH_REPORT.md` (architecture) — use `graphify query` for symbol lookup.
- Downstream dependency: the user's auto-memory `project-dynamic-chapter-planner` + `project-dynamic-planner-handoff` describe the re-plannable planner this upstream work unblocks (FAs + holidays + exam-period blocking delivered here; SA support NOT — see D-16).

## Step 7 — Things to ask the user before acting
- Production deployment (default: no).
- Schema changes not in `02-data-model.md`.
- New external dependency.
- Re-seeding.
- Any move to build Summative Assessment slots/generation/results — explicitly deferred (D-16).

## Step 8 — How to start a phase as a fresh agent
1. Read this onramp + the active phase file.
2. Open the phase bead (`feat-exam-periods-fa-phase-N-<slug>`), status `in_progress`.
3. `git fetch origin staging && git checkout -b feat/exam-periods-fa-phase-N-<slug> origin/staging`.
4. Implement features in numbered order (F-N.1, F-N.2, …); acceptance in the phase doc.
5. Update Step 5 Current State in the same PR.
6. Merge → watch both deploys → mark phase ✅ → close bead → open next phase's bead.

## Step 9 — Keep the plan files alive (HARD RULE)
- Land a feature → update Step 5 (same PR).
- New decision the plan didn't anticipate → add a D-N to `01-decision-log.md`.
- Schema change → update `02-data-model.md` in the same PR as the migration SQL.
- New term → add to `00-glossary.md`.
- Self-check before closing a bead: Current State accurate? new decisions logged? data model matches schema? a fresh agent could identify the next step? If any fails, fix before closing.
