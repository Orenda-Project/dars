# Data Model — Dynamic Chapter Planner

Ground truth for schema. Migration SQL cites this doc; this doc reflects the SQL in the
same PR. Migrations are append-only.

## Existing tables (unchanged shape, listed for reference)

`class_lesson_slots` (post-migration 20260610, before this feature):
`id, org_id, cst_id, position, slot_type, lp_type, topic_id, anchor_date, book_chapter_id,
generated_lp_id, page_start, page_end, status('planned'|'taught'|'skipped'),
created_at, updated_at` · `UNIQUE (cst_id, position)`.

`class_assessment_slots`:
`id, org_id, cst_id, position, assessment_type('formative'|'summative'), anchor_date,
book_chapter_id, generated_exam_id, page_start, page_end,
status('scheduled'|'completed'|'skipped'), created_at, updated_at` · `UNIQUE (cst_id, position)`.

`sub_slo_mastery`: `id, cst_id, sub_slo_id, class_assessment_slot_id, mastery_percent NUMERIC,
assessed_on DATE`. Written by `mastery_service.submit_exam_results`.

## Deltas added by this feature

### Phase 1 migration — `20260612000000_dynamic_planner_slot_origin.sql`

One `ADD COLUMN` per `ALTER TABLE` (D-12): sqlite rejects a single `ALTER TABLE … ADD
COLUMN a, ADD COLUMN b` (`near ",": syntax error`); Postgres accepts both forms, so the
split is the portable one used by the shipped migration.

```sql
ALTER TABLE class_lesson_slots
  ADD COLUMN origin TEXT NOT NULL DEFAULT 'breakdown'
    CHECK (origin IN ('breakdown', 'reteach', 'manual'));
ALTER TABLE class_lesson_slots
  ADD COLUMN reteach_for_sub_slo_id UUID REFERENCES sub_slos(id);
ALTER TABLE class_lesson_slots
  ADD COLUMN flex BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE class_assessment_slots
  ADD COLUMN origin TEXT NOT NULL DEFAULT 'breakdown'
    CHECK (origin IN ('breakdown', 'reteach', 'manual'));
```

- `origin` — provenance (D-1 seed = `'breakdown'`; reteach inserts/consumes = `'reteach'`;
  future manual edits = `'manual'`). On `class_assessment_slots` for read symmetry even
  though assessments aren't dynamically inserted yet.
- `reteach_for_sub_slo_id` — the sub-SLO a reteach slot re-covers (NULL otherwise). FK to
  `sub_slos` (D-10).
- `flex` — droppable buffer lesson slot (D-3/D-4). Only on `class_lesson_slots` (flex slots
  are revision lessons, never assessments).

**sqlite note (D-11):** plain `ADD COLUMN` with literal defaults and a CHECK — portable to
sqlite once split one-per-statement (above). `UUID` columns are TEXT in sqlite (existing
pattern); the FK stays inline. No `gen_random_uuid()` here, so no dialect split on defaults.
Verified clean against an in-memory sqlite DB (existing rows default to `origin='breakdown'`,
`flex=false`; the CHECK rejects bad origins).

### Phase 2 migration — `20260613000000_org_completion_target.sql`

**D-14 (frozen 2026-06-12):** `completion_target` is an **org default only** — no per-CST
override (deferrable later). One place for org-wide policy; simplest schema. This supersedes
the earlier "org default + optional per-CST override, confirmed at phase start" placeholder.

```sql
ALTER TABLE organizations
  ADD COLUMN default_completion_target NUMERIC NOT NULL DEFAULT 0.80;
```

- `default_completion_target` — the fraction of a chapter's teaching days planned into
  MANDATORY content (D-3). `0.80` = plan to 80%, keep 20% as interleaved flex buffer (D-4).
  `chapter_plan_service.build_plan_request` reads the CST's org value at break-it-down and
  computes the per-chapter `mandatory_budget = round(teaching_days * target)`
  (`compute_buffer_budget`); the remainder `period_count - mandatory_budget` is the flex count
  the planner interleaves (F-2.2/F-2.3). Lower = more buffer.

**sqlite note (D-11):** single `ADD COLUMN` with a literal NUMERIC default — no PG-only
syntax, applies on both Postgres (Railway) and sqlite (planner/budget tests run against an
in-memory DB; NUMERIC affinity round-trips a float). One column, so the D-12 one-per-ALTER
split is not needed.

### Phase 3 — no schema change

Reteach reuses `sub_slo_mastery` (read — `mastery_percent` below `RETEACH_MASTERY_THRESHOLD`
surfaces the suggestion, F-3.1), `cst_sub_slo_coverage` (needs-rework flip via the lightweight
path: `status='not_taught'`), and the Phase-1 slot columns above (`origin='reteach'`,
`reteach_for_sub_slo_id`, `flex` for consume). The threshold is a code constant
(`RETEACH_MASTERY_THRESHOLD = 60.0`), not a column. The overflow consequence (D-17) is a
read-time projector delta, not stored.
