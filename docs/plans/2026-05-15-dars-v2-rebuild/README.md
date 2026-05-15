# Dars v2 Rebuild — Plan

**Authored:** 2026-05-15  
**Status:** Draft (pending kickoff)  
**Target environment:** staging only — production stays untouched (see [Decision 34](01-decision-log.md))

## Why this plan exists

Dars today has a half-built data model: SLOs are first-class, but they aren't linked to slots; books have OCR but nothing uses it; chapter breakdown logic exists but produces lesson types LP Assistant doesn't understand; the teacher app uses mocks. The fix isn't incremental — it's a rebuild on the same code-base with a corrected data model and a real generation pipeline.

This plan delivers Dars v2: an SLO-centric, sequence-driven, multi-tenant lesson-planning backend, fully integrated with LP Assistant v3 and UG_EG v2, with a sample teacher app and an org admin dashboard.

## Scope summary

- **Backend:** new data model (`Org → School → CST`, `Curriculum → Grade → Subject → SLO/SubSLO/Book → Chapter → Topic`), seeded with a believable "Dars Curriculum, English G1" fixture. Real generation pipeline using `page_content` and `lp_type`. LP/Exam caching at the curriculum level. Webhook + manual-poll handlers.
- **Teacher app:** full rewrite, no auth (it's a sample integration). Real data, real LPs (cached or generated on demand).
- **Dashboard:** full rewrite. Email/password org-admin login. Breakdown editor (review draft, fork from global, edit per-chapter days, anchor admin-level dates). Generation progress UI, SLO coverage reports.
- **Production:** untouched in this plan. Plan for prod migration is a later, separate effort.

## Repository layout for this plan

```
docs/plans/2026-05-15-dars-v2-rebuild/
├── README.md                           ← you are here
├── 00-glossary.md                      ← every term defined; read first
├── 01-decision-log.md                  ← 60+ decisions with rationale
├── 02-data-model.md                    ← final schema + migration SQL
├── 03-phase-1-foundation.md            ← data model + seed + read API
├── 04-phase-2-breakdown-engine.md      ← port Schema; breakdown CRUD + fork + sequence
├── 05-phase-3-generation-pipeline.md   ← LP/Exam gen, caching, tagging, costs
├── 06-phase-4-teacher-app.md           ← teacher-app rewrite
├── 07-phase-5-dashboard.md             ← dashboard rewrite
├── 08-reference-lp-assistant-api.md    ← frozen LP Assistant API spec (re-verify SHA when stale)
└── 09-reference-ug-eg-api.md           ← frozen UG_EG API spec
```

**Project onramp lives at [../../REBUILD.md](../../REBUILD.md) (repo root).** A new agent should be pointed at REBUILD.md, not directly at this README.

## Document precedence

If two documents disagree, the higher-up doc wins:

```
1. 01-decision-log.md         (D-N references are canonical)
2. 02-data-model.md           (schema is the ground truth)
3. 00-glossary.md             (terminology)
4. phase docs (03..07)        (specs)
5. 08, 09 reference docs      (external API surface — re-verify if stale)
6. running code               (last; may be ahead or behind the plan)
```

If you find a real conflict, raise it with the user before resolving. Don't silently pick a side.

## Where to start (by role)

**Executor (Claude or other agent):** read 00 → 01 → 02 → start whichever phase is unblocked. Each phase document is self-contained — you should not need to re-derive decisions made in 01. If a decision is unclear, escalate to the user; don't guess.

**Reviewer (user):** read 00 → 01 → 02 → skim phases. Decision log is the most important review surface — if any decision feels wrong, fix it there *before* the phase that depends on it starts.

**Returning to the plan after time has passed:** decision log + glossary keep terminology stable. If anything in the code conflicts with the glossary, the code is wrong; if the code conflicts with a decision, the decision is wrong (open a discussion to revise the log).

## Phase order and dependencies

```
Phase 1 (foundation)
   │
   ▼
Phase 2 (breakdown engine) ─┐
                            │
                            ▼
Phase 3 (generation pipeline)
                            │
                            ▼
Phase 4 (teacher app)
                            │
                            ▼
Phase 5 (dashboard)
```

Each phase ends with a staging deploy. Don't start phase N+1 until phase N is on staging and verified ([Decision 51](01-decision-log.md)). Each phase opens one bead ([Decision 54](01-decision-log.md)) and closes when staging is green.

## Conventions inside phase documents

Each phase is a sequence of **features**. Each feature has:

- **Motivation** — what user-visible or system-visible problem this solves
- **Spec** — exact endpoints, tables, services, FE pages
- **Test plan** — unit / integration tests; manual checks
- **Acceptance** — what makes this feature "done"

Features within a phase are ordered. A feature can depend only on earlier features in its phase or any feature in a prior phase.

## How to start a phase (for executing agents)

When the user says "start phase N" (or you arrive at this state with everything else covered):

1. Read [REBUILD.md](../../REBUILD.md) (repo root) end to end if you haven't already — that's the operating manual.
2. Read this plan's [00-glossary.md](00-glossary.md), [01-decision-log.md](01-decision-log.md), [02-data-model.md](02-data-model.md).
3. Read the phase file end to end: [03-phase-1-foundation.md](03-phase-1-foundation.md) · [04-phase-2-breakdown-engine.md](04-phase-2-breakdown-engine.md) · [05-phase-3-generation-pipeline.md](05-phase-3-generation-pipeline.md) · [06-phase-4-teacher-app.md](06-phase-4-teacher-app.md) · [07-phase-5-dashboard.md](07-phase-5-dashboard.md).
4. Open the phase's bead (`feat-v2-phase-N-{slug}`) per the dars beads workflow.
5. Branch from `staging` (NEVER main): `git fetch origin staging && git checkout -b feat/v2-phase-N-{slug} origin/staging`.
6. Implement features in the order the phase doc lists them. One PR per feature (or per logical change). PR target: `staging`.
7. As you land each feature, update REBUILD.md's "Current state" table. Update the decision log if you make any new architectural decision. Update the data model doc if the schema shifts. (See REBUILD.md Step 9.)
8. When the phase is done: mark ✅ in REBUILD.md, close the bead, open the next phase's bead if proceeding.

## What's NOT in this plan

- Production migration ([Decision 34](01-decision-log.md) — separate effort)
- Multi-curriculum org support ([Decision 25](01-decision-log.md) — one curriculum per org for v1)
- Per-student mastery ([Decision 31](01-decision-log.md) — class-level only)
- Teacher authentication (see Q9 in [01-decision-log.md](01-decision-log.md) — teacher app is auth-free sample)
- Real i18n ([Decision 37](01-decision-log.md) — English UI, RTL content only)
- Real time tracing/Sentry ([Decision 44](01-decision-log.md) — structured logs only)
- Rate limiting ([Decision 45](01-decision-log.md) — observe, don't throttle in v1)
- Breakdown versioning beyond immutable records ([Decision 18](01-decision-log.md) — no "pull updates" UI)
- LP regeneration on demand ([Decision 48](01-decision-log.md) — teachers get cached LPs only)
