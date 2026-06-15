---
type: plan
last_verified: 2026-06-12
owner: hataf
status: proposed
bead: feat-dynamic-chapter-planner
---

# Dynamic Chapter Planner — buffer-budgeted, re-plannable class plans

## Problem

The chapter planner is a **one-shot breakdown**: `generate_chapter_plan` materializes a
chapter's slots into `class_lesson_slots` + `class_assessment_slots` once, then refuses
to touch them (`chapter_plan_service.py:310-323`, *"chapter already broken down; clear it
first to regenerate"*). Reality moves after planning:

1. **Lost periods** — teacher takes a holiday / is absent / a strike closes school.
2. **Reteach** — a formative assessment shows the class failed a sub-SLO and must re-cover it.

Both should adjust the *forward* plan without nuking taught history.

## What's already true (verified on staging, post-#136–#141)

These are load-bearing facts the design rests on — don't re-derive:

- **Dates are never stored.** `projector.py:project_cst_schedule` derives every slot's date
  at read time from `(slots ordered by position, teaching_days, holidays)`. A holiday added
  anywhere re-projects the same slots onto later dates automatically.
- **Holiday/exam edits already propagate live** (#141 / D-21). The projector unions
  `get_effective_holidays` with `breakdown_holidays` + `exam_periods` off the published
  `syllabus_breakdowns` (`projector.py:~224`). So **Case 1 (lost periods) needs no planning
  change at all** — it's pure projection. The only consequence is *overflow*
  (`ProjectedSlot.is_overflow=True`) when the tail runs out of teaching days.
- **Class slots are already untethered from the template.** `breakdown_slot_id` was dropped
  (migration 20260604). The class slots ARE the live plan; the breakdown is a seed. The
  "class slots own the live plan" model is already physically the schema.
- **Lessons + assessments share ONE position sequence per CST.** Both tables have
  `UNIQUE (cst_id, position)` and the projector merges them by position
  (`chapter_plan_service.py:348-414`). Any insert/remove must renumber **both tables together**.
- **Mastery is already computed.** `mastery_service.submit_exam_results` writes per-sub-SLO
  `mastery_percent` into `sub_slo_mastery`. No threshold constant exists yet.
- **On-demand LP generation shipped** (#133): `get_or_generate_lp` + the per-slot route/button.
  A reteach slot's LP rides this path.
- **`reorder_path` / taught-lock no longer exist** — removed when the teacher path became a
  read-only mirror of the published breakdown. The taught-lock invariant is **built fresh** here.

## The core idea — buffer-budgeted planning

Planning to fill 100% of teaching days means *any* slip pushes the tail past year-end (a hard
wall: board/annual exams are fixed). Instead:

- Plan **mandatory content into ~70–80% of teaching days** (completion target = a knob,
  per-CST/grade; foundational grades want more buffer, exam grades want the syllabus done early).
- Fill the remaining slack with **flex slots** (revision / consolidation), tagged droppable.
- **Buffer is interleaved per-chapter, NOT a trailing end-of-year block** — a trailing block
  can't absorb an October slip. Slack only helps if it sits downstream *and nearby*. Each
  chapter carries flex proportional to its length; a thin **shared remainder pool** covers
  cross-chapter summatives and end-of-term. Short chapters round to zero and lean on the pool.
- **Reteach consumes the chapter's own flex slot first, the shared pool second, and only
  shifts/overflows when both are dry.** Net date change stays zero until local slack runs out
  — so overflow (and the human alert) only fires when a class is genuinely, deeply behind.

## Ground-truth guardrails (Pakistani gov / low-cost schools)

- **Never silently bleed past year-end.** Pair every reteach insert with its consequence in
  the same UI step ("uses Chapter 4's spare revision day" / "pushes revision out of the year —
  drop or compress?").
- **Lightweight reteach is the default.** Often it's 15 min folded into the next class, not a
  whole new period. Offer fold-into-next-slot / tag-coverage-needs-rework as default; full-slot
  insertion is the heavy option. Else teachers route around it and coverage data goes fictional.
- **Reteach is teacher-initiated + confirmed, never auto-applied.** The mastery signal is a
  suggestion badge, not an action.

---

## Phases

### Phase 1 — Slot-mutation foundation (the load-bearing piece)

Both cases reduce to *mutate the realized slot sequence; let the projector absorb the dates*.

**Migration** (`<ts>_dynamic_planner_slot_origin.sql`):
- `class_lesson_slots`: add
  `origin TEXT NOT NULL DEFAULT 'breakdown' CHECK (origin IN ('breakdown','reteach','manual'))`,
  `reteach_for_sub_slo_id UUID REFERENCES sub_slos(id)`,
  `flex BOOLEAN NOT NULL DEFAULT false`.
- `class_assessment_slots`: add the same `origin` column (symmetry; assessments aren't
  inserted yet but reads shouldn't special-case).

**New `breakdown/slot_mutation_service.py`:**
- `insert_lesson_slot(conn, cst_id, after_position, *, topic_ids, lp_type, origin, reteach_for_sub_slo_id=None, flex=False)`
  — open a gap at `after_position+1` by renumbering both tables' rows `> after_position`
  (descending order, or a deferred/temp-offset pass) inside one tx to respect
  `UNIQUE (cst_id, position)`; insert the new `planned` lesson + its `class_lesson_slot_topics`.
- `remove_slot(conn, cst_id, position)` — only `planned`/`scheduled` slots; delete + renumber tail.
- `consume_flex_slot(conn, cst_id, after_position, *, reteach_for_sub_slo_id, lp_type)` —
  find the nearest downstream `flex=true planned` lesson slot, repurpose it in place (set
  `origin='reteach'`, `flex=false`, `reteach_for_sub_slo_id`, rewrite topics) instead of inserting.
  Returns whether a flex slot was consumed (no shift) or a full insert is needed (shift).

**Fresh taught-lock invariant:** reject any mutation at or before the CST's
`max(position) WHERE status IN ('taught','completed')`. Only future `planned`/`scheduled`
slots may move. This is the same guarantee the removed `reorder_path` had — rebuilt.

**Tests** (`tests/test_slot_mutation_service.py`): **sqlite-runnable** (the user added sqlite3
so these don't need Postgres). Cover: insert renumbers both tables; taught-lock rejects
insert-into-past; remove only-planned; consume_flex prefers nearest downstream flex; position
uniqueness holds through renumber. Keep SQL portable (raw SQL is the norm in `breakdown/`).

### Phase 2 — Buffer-budgeted planner

- `planner_models.PlanUnit`: allow `slot_type='flex'` (or a `flex: bool` on lesson units);
  flex units are revision/consolidation lessons, droppable.
- `planner_prompts.py`: change the contract from "fill `period_count`" to "plan mandatory
  content, then add flex slots to reach `period_count`, targeting ~`completion_target`% of the
  chapter's teaching days as mandatory." Distribute flex within the chapter (interleaved, after
  topic clusters), not all at the end.
- `chapter_plan_service`: compute per-chapter mandatory budget from a `completion_target` knob
  (new column on CST or org default; default ~0.8), persist flex lessons with `flex=true`.
  Thin shared remainder pool = whatever slack the per-chapter rounding leaves, placed end-of-term.

### Phase 3 — Reteach trigger

- Threshold constant (e.g. `RETEACH_MASTERY_THRESHOLD = 60.0`) — below it on `sub_slo_mastery`
  surfaces a **suggestion badge** on the FA's slot in the teacher app.
- Teacher confirms → `consume_flex_slot` (preferred, no shift) else `insert_lesson_slot`
  (shift, with the overflow consequence shown) → LP via `get_or_generate_lp`
  (`lp_type='revision'`, `origin='reteach'`, `reteach_for_sub_slo_id` set).
- Lightweight option: "mark sub-SLO needs-rework" flips `cst_sub_slo_coverage` without a new
  slot, for the fold-into-next-class case.

## Out of scope (for now)

- Inserting *assessment* slots dynamically (only lesson/reteach inserts in Phase 1).
- Auto-applying reteach without teacher confirmation.
- Re-running the whole-chapter planner (we mutate, never regenerate, to preserve taught history).

## Risks / open questions

- **Renumber under `UNIQUE (cst_id, position)`**: a naive `UPDATE ... SET position = position+1`
  can transiently collide. Resolve with descending-order updates or a two-step offset
  (`+1000000` then settle). Verify the chosen approach works on **both** asyncpg and sqlite.
- **`completion_target` home**: per-CST column vs per-grade default vs org setting. Leaning
  org-default + optional per-CST override; confirm during Phase 2.
- **Overflow UX** lives in the webapp (read `is_overflow` from the projector) — a thin slice
  ships with Phase 1 so the holiday story is visible even before reteach exists.
