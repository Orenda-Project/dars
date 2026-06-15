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
