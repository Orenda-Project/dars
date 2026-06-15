# Decision Log — Dynamic Chapter Planner

Canonical. Decisions are frozen — to revise, mark the old "Superseded by D-N+1 on DATE"
and add the new; both stay.

**D-1: Class slots own the live plan; the Syllabus Breakdown is a one-time seed.**
*Rationale:* the projector already reads only class slots, `breakdown_slot_id` was already
dropped (migration 20260604), and divergence must be local to one CST (a reteach in one
class can't leak into the template or another class). *Apply:* all mutation happens on
`class_lesson_slots`/`class_assessment_slots`; never re-read the breakdown for slot content.
*Decided:* 2026-06-10 (design session).

**D-2: Holidays/lost periods need NO planning change — they are pure projection.**
*Rationale:* `project_cst_schedule` re-derives dates from the live teaching-day set, and
post-#141 it unions `breakdown_holidays` + `exam_periods` live. Adding a holiday re-flows
the same slots onto later dates automatically. *Apply:* Case 1 is handled by existing code;
this feature only adds **overflow surfacing** (read `is_overflow`). *Decided:* 2026-06-10.

**D-3: Buffer-budgeted planning — plan mandatory content into ~70–80% of teaching days;
fill the rest with droppable flex slots.** *Rationale:* planning to 100% means any slip
overflows past the fixed year-end (board/annual exams). A buffer absorbs holidays + reteach.
*Apply:* planner computes a mandatory budget per chapter from a completion-target knob and
emits flex slots to reach `period_count`. *Decided:* 2026-06-10.

**D-4: Buffer is interleaved per-chapter, NOT a trailing end-of-year block.**
*Rationale:* slack only absorbs a slip if it sits downstream AND nearby; an October slip
can't reach a March buffer. Reteach demand is chapter-local (a failed FA is on that chapter's
SLOs). *Apply:* each chapter carries flex proportional to its length; a thin shared remainder
pool covers cross-chapter summatives + end-of-term; short chapters round to zero flex and
lean on the pool. *Decided:* 2026-06-10.

**D-5: Reteach consumes the chapter's own flex slot first, the shared pool second, and only
shifts/overflows when both are dry.** *Rationale:* keeps net date change at zero until local
slack is exhausted, so overflow (and the human alert) fires only when a class is genuinely
behind. *Apply:* `consume_flex_slot` before `insert_lesson_slot`. *Decided:* 2026-06-10.

**D-6: Mutate the sequence; never regenerate the chapter.** *Rationale:* full regenerate
nukes `taught` status and sub-SLO coverage. *Apply:* keep the "already broken down" refusal
(`chapter_plan_service.py:310-323`) for the initial break-it-down; add surgical
insert/remove/consume primitives alongside it. *Decided:* 2026-06-10.

**D-7: Build the taught-lock invariant fresh (the old `reorder_path` lock was removed).**
*Rationale:* the teacher path became a read-only mirror of the published breakdown, so
`reorder_path` + its lock no longer exist. *Apply:* `slot_mutation_service` rejects any
mutation at/before the CST's last `taught`/`completed` position. *Decided:* 2026-06-12
(verified against staging).

**D-8: Lessons + assessments share ONE position sequence; insert/remove renumber BOTH tables
in one transaction.** *Rationale:* both tables carry `UNIQUE (cst_id, position)` over the
same number space and the projector merges by position. *Apply:* renumber descending (or
two-step offset) to avoid transient unique-collision; verify on asyncpg AND sqlite.
*Decided:* 2026-06-12.

**D-9: Reteach is teacher-initiated and confirmed; the mastery signal is a suggestion only.**
*Rationale:* FAs are often informal/late-graded and the teacher owns the "did they get it"
call; auto-inserting makes coverage data fictional. *Apply:* below-threshold
`sub_slo_mastery` → suggestion badge → teacher confirm → mutation. Default offered action is
**lightweight** (fold-into-next / mark needs-rework); full-slot insert is the heavy option.
*Decided:* 2026-06-10.

**D-10: Reteach LP rides the shipped on-demand path (`get_or_generate_lp`, #133).**
*Rationale:* don't build a second generation path. *Apply:* reteach slot generates with
`lp_type='revision'`, `origin='reteach'`, `reteach_for_sub_slo_id` set. *Decided:* 2026-06-12.

**D-11: New mutation tests run on sqlite (no Postgres dependency).** *Rationale:* the user
added sqlite3 specifically so slot-mutation logic is testable without a live DB; the
`breakdown/` layer uses portable raw SQL. *Apply:* `tests/test_slot_mutation_service.py`
provisions an in-memory/file sqlite DB; keep all mutation SQL portable. *Decided:* 2026-06-12.

**D-12: Renumber via two-step large-offset; generate slot ids in Python; one ADD COLUMN
per ALTER.** *Rationale (renumber):* a single `UPDATE ... SET position = position ± 1` can
transiently violate `UNIQUE (cst_id, position)` mid-statement on sqlite (which checks the
constraint per-row); rather than depend on Postgres-only statement-end checking we keep ONE
portable path. *Apply:* `_shift_positions` first parks affected rows out of the live range
(`position += 1_000_000`), then settles them to their final `±1` — collision-free on both
asyncpg and sqlite, verified by `test_insert_preserves_uniqueness_across_renumber`.
*Rationale (ids):* the live tables get `id` from a `gen_random_uuid()` DEFAULT + `RETURNING`,
which the sqlite test schema has no equivalent for (RETURNING yields NULL). *Apply:*
`insert_lesson_slot` generates `uuid4()` in Python and inserts it explicitly — identical on
Postgres (the column accepts an explicit id), portable to sqlite. *Rationale (DDL split):*
sqlite rejects multiple `ADD COLUMN` clauses in one `ALTER TABLE` (Postgres accepts both);
verified `ALTER ... ADD COLUMN x, ADD COLUMN y` → `near ",": syntax error` on sqlite.
*Apply:* migration `20260612000000_dynamic_planner_slot_origin.sql` uses one `ALTER TABLE …
ADD COLUMN` statement per column; `02-data-model.md` shows the split form. *Decided:* 2026-06-12.

**D-13: Overflow surfacing (F-1.4) rides the existing CST timeline read, not a new endpoint.**
*Rationale:* `GET /api/v2/csts/{cst_id}/timeline` already runs the projector and carries
per-item `is_overflow`; adding a count there is the thinnest seam and avoids a second route
+ a second projector call. *Apply:* `CstTimelineResponse.overflow_count` (additive,
default 0) tallies `is_overflow` over the already-computed items; no new projection logic.
A CST whose slots exceed its teaching days reports `overflow_count > 0`; one that fits reports
0. *Decided:* 2026-06-12.

**D-14: `completion_target` lives as `organizations.default_completion_target NUMERIC NOT NULL
DEFAULT 0.80` — ORG DEFAULT ONLY, no per-CST override.** *Rationale:* simplest schema, one
place for org-wide policy; a per-CST override can be added later if a real need appears
(deferrable). Supersedes the `02-data-model.md` Phase 2 placeholder ("org default + optional
per-CST override, confirmed at phase start"). *Apply:* migration
`20260613000000_org_completion_target.sql` adds the column; `chapter_plan_service.build_plan_request`
reads the CST's org value and computes per-chapter `mandatory_budget = round(teaching_days *
target)`, passing it (alongside `period_count`) to the planner. Portable column: literal default,
no PG-only syntax, applies on sqlite. *Decided:* 2026-06-12 (frozen by user).

**D-15: Flex is a `flex: bool` on `PlanUnit`, NOT a new `slot_type` enum value.** *Rationale:*
adding `'flex'` to `VALID_SLOT_TYPES` would ripple through every `slot_type` validator and the
persistence branch in `chapter_plan_service`; a boolean leaves `slot_type='lesson'` untouched and
adds one cheap invariant. The phase-2 doc (F-2.1) already leaned this way. *Apply:* `PlanUnit.flex`
(default `False`); a model validator enforces `flex=True ⇒ slot_type='lesson' AND lp_type='revision'`
(a flex slot is always a revision/consolidation lesson — D-3/D-4). `_build_unit` reads `flex` from
the LLM dict; `generate_chapter_plan` persists it to `class_lesson_slots.flex` with
`origin='breakdown'`. Flex counts toward `period_count` (1 slot = 1 day). *Decided:* 2026-06-12.

**D-16: The mandatory budget is advisory steering for the planner, not a hard post-validate
invariant.** *Rationale:* the planner must still satisfy the frozen D-8 invariants (exactly
`period_count` units, full SLO coverage, valid permutation) — those are non-negotiable and
validator-checked. The flex/mandatory split is *guidance* the prompt asks the LLM to honour
("plan mandatory content into ~`mandatory_budget` days, then fill the remainder with flex revision
slots to reach `period_count`"); we do NOT reject a plan for landing a slot or two off the budget,
because a chapter with more SLOs than the budget allows must still cover them all (coverage wins
over buffer). The deterministic budget math (per-chapter `round(days*target)`, flex proportional to
length, short chapters → zero flex leaning on the shared end-of-term pool) lives in
`build_plan_request` (`compute_buffer_budget`) and is unit-tested directly; it is what we *ask*
for, and the persisted `flex` flags reflect what the planner returned. *Decided:* 2026-06-12.

**D-17: The reteach overflow consequence is computed by a dry-run projector delta around the
heavy mutation.** *Rationale:* F-3.2 requires the response to say whether inserting a reteach slot
pushes a tail slot out of the year-end and which one. The projector (`project_cst_schedule`)
already owns `is_overflow` per slot; rather than re-derive year-end arithmetic we read the
projection BEFORE the mutation (baseline overflow set), apply the mutation, read it AFTER, and
report the delta: `overflow_count` before/after, the positions that newly overflow, and the first
newly-overflowing position. `consume_flex` shifts nothing, so its consequence is always `None`;
only `insert` (shift) can push the tail. Computed within the same connection the action runs in so
the "after" projection sees the inserted slot. *Apply:* `reteach_service` returns a `ReteachResult`
with `path` (`'lightweight'|'consume_flex'|'insert'`), `slot_id`, and `consequence` (None for
lightweight/consume; `{overflow_before, overflow_after, newly_overflowed_positions,
first_overflow_position}` for insert). *Decided:* 2026-06-12.

**D-18: The teacher-app reteach UI lives on the mastery-entry/results page (NOT a separate
badge on the FA timeline card), and the overflow consequence is shown as a calendar outcome,
not raw numbers.** *Rationale (placement):* F-3.3's "badge on the FA slot card" is the spirit
("class struggled with X — reteach?"), but the suggestion is only meaningful *after* grading,
and the results page (`…/assessments/[slot_id]/results/page.tsx`) is exactly where grading
finishes — the teacher is already there with full context. Surfacing the panel inline right
after a successful `submitExamResults` (and re-fetching on load when the slot is already
`completed`, so a returning teacher still sees it) keeps the confirm step one screen away from
the data that triggered it, instead of asking the teacher to navigate back to a timeline badge.
The FA timeline card can link here later; this is the highest-context home for the confirm
step. *Rationale (phrasing):* `OverflowConsequence` ships raw integers
(`newly_overflowed_positions`, `first_overflow_position`). A teacher doesn't read "positions";
they read days and lessons. We translate each path into a one-line calendar outcome —
lightweight → "re-cover in your next class, schedule unchanged"; `consume_flex` → "added a
reteach lesson using a spare revision day, schedule unchanged"; `insert` with no overflow →
"added on a new day, everything still fits"; `insert` with overflow → "pushed N later
lesson(s) past the end of the school year, starting at lesson #first_overflow_position —
you'll need to drop a revision day, move an exam, or trim coverage." This is the "what falls
off" moment the spec asks to make legible. *Apply:* presentational molecule
`webapp/components/molecules/reteach-panel.tsx` (hook-free, page owns state per the layer
rules — mirrors `mastery-entry-template`); per-sub-SLO confirm with lightweight pre-selected
(recommended); after acting, the row shows the outcome and disables further action; declining
("Not now") leaves the plan untouched. NOTE: the shipped client methods are
`slots.getReteachSuggestion` / `slots.confirmReteach` (the `slots` namespace in `dars-api.ts`),
not `mastery.*`; the UI consumes the contract as shipped — no signature change. *Decided:*
2026-06-15.
