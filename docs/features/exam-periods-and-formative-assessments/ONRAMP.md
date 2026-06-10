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
| Phase 1 — Exam Periods & Breakdown Holidays (`03-...`) | ✅ Shipped | #136 | Squash-merged to staging (`32c6493`); both Railway deploys SUCCESS — migration applied, `exam_periods` + `breakdown_holidays` live |
| Phase 2 — Planner emits FAs (`04-...`) | ✅ Shipped | #137 | Squash-merged to staging (`decfa19`); backend deploy SUCCESS, webapp SKIPPED (healthy — untouched) |
| Phase 3 — FA → Exam Generator inputs (`05-...`) | ✅ Shipped | #138 | Squash-merged to staging (`40e77dc`); **root Claude fixed a latent broken-join bug** (D-18) the agent inherited; 260 passed / 60 skipped; webapp typecheck/build clean |

**FEATURE COMPLETE — all three phases shipped to staging.** The DB-gated FA exam tests (D-18 SQL) run on the seeded staging deploy. Remaining follow-ups, all documented and out of original scope: (a) Summative Assessments (D-16 — exam periods are pure calendar blocks today; SAs = slots + summative generation + per-SLO results, the upstream work the downstream dynamic planner waits on); (b) per-slot editable FA exam config (D-10, default-config only today); (c) `/today` endpoint `exam_status` so the Today card FA button reflects real status.

**Implementation notes (Phase 3):** `DEFAULT_FA_CONFIG` per subject + generic fallback (D-10). `get_or_generate_exam_for_assessment_slot` mirrors `get_or_generate_lp`, reusing the exam service's `load_assessment_slot_context` / `get_or_generate_exam` / cache-key / dispatch — the slot's `generated_exam_id` is linked by the **service** (`_link_slot_to_exam`), not the webhook. Endpoint `POST /api/v1/class-assessment-slots/{slot_id}/generate-exam`. Teacher "Generate exam" button + `ExamViewer` mirror the per-slot LP affordance. **Three plan-vs-code corrections logged:** D-18 (CST has no curriculum_id/grade_id — resolve via org/class; latent bug fixed), D-19 (`generation_type='class_assessment'`, not the planned `'formative'` — enum has no such value), D-20 (`ExamRequest` has no `sub_slo_statements` field, so FA exams don't send them). Known follow-up: the `/today` endpoint's `AssessmentSlotEntry` has no `exam_status`, so the Today card's FA button defaults to "Generate exam" (the timeline tab reads real status) — a small add later.

**Implementation notes (Phase 1):** breakdown resolution happens *internally* in `chapter_slot_count` / `project_cst_schedule` (no call-site signature change; projector uses a lazy import + inline `_resolve_published_breakdown_id` to dodge an import cycle); no separate `exam_overlap` advisory (a chapter inside an exam/holiday window surfaces via the existing `zero_teaching_days` warning, D-4). Endpoints under `/api/v2/syllabus-breakdowns/{id}/exam-periods` and `/holidays`. `resolve_breakdown_holidays` in `chapter_calendar.py` is now unused but left defined.

**Implementation notes (Phase 2):** `PlanUnit.slot_type` defaults to `'lesson'` (back-compat). FA units carry no `lp_type`; an echoed one is silently dropped at parse (`_build_unit`) while `validate_plan` still hard-rejects it as defence-in-depth (D-17). FA persists as `class_assessment_slots (org_id, cst_id, position, assessment_type='formative', book_chapter_id, status='scheduled')` + `class_assessment_slot_topics`, sharing the lesson/assessment position sequence. The teacher timeline (`class-timeline-tab.tsx`) already renders FA slots (rose `◆ FA` badge) — no frontend change needed. `generated_exam_id` stays NULL until Phase 3.

**Reminder on running tests:** the repo's root `.env` points `DATABASE_URL` at the *live staging Postgres*, which is NOT seeded for tests — `make test` runs the DB-gated e2e/smoke suites against it and they fail spuriously on auth. Always run the suite with `env -u DATABASE_URL uv run pytest` (from `server/`) so DB-gated tests skip as designed. Green baseline: 249 passed / 57 skipped after Phase 2.

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
