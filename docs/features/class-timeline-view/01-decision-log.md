# Decision Log — Class Timeline View

Decisions are frozen. To revise: ask the user, mark the old entry "Superseded by D-N on YYYY-MM-DD", add the new one. Both stay.

---

**D-1: Unify lessons + assessments into one dated timeline.** *Rationale:* The two-tab split hides the real teaching order — lessons and assessments interleave by `position` on the calendar, and the projector already merges them, but the UI throws that away. A single chronological list mirrors how teaching actually unfolds. *Apply:* Phase 2 replaces the Lessons + Assessments tabs with a Timeline tab. *Decided:* 2026-06-01 (plan).

**D-2: Dates are the spine, sourced from the projector.** *Rationale:* `project_cst_schedule` already computes a `projected_date` per slot honouring timetable + holidays + anchors. The UI must not re-derive dates client-side (would drift from the projector). Every timeline row carries the projector's date. *Apply:* Phase 1 endpoint joins projector output to slot rows; Phase 2 renders date as primary. *Decided:* 2026-06-01 (plan).

**D-3: New backend endpoint `GET /api/v2/csts/{cst_id}/timeline`.** *Rationale:* No existing endpoint returns merged + dated + status-bearing slots. Doing the merge server-side keeps date logic next to the projector (single source of truth) and gives the frontend one clean fetch. *Apply:* Phase 1, in `router_class_actions.py` (alongside the existing lesson-slots / assessment-slots list endpoints). *Decided:* 2026-06-01 (plan).

**D-4: Timeline item is a discriminated union on `kind`.** *Rationale:* Lessons and assessments share position/date/chapter/status shape but differ in fields (lesson: `lp_type`, `slot_type`, single `topic_title`, `lp_status`; assessment: `assessment_type`, `topic_titles[]`, `exam_status`). A `kind`-tagged union keeps both renderable in one list without lossy flattening. *Apply:* Phase 1 response schema; Phase 2 rendering switches on `kind`. *Decided:* 2026-06-01 (plan).

**D-5: Reuse `project_cst_schedule` verbatim; do not re-query slots for dates.** *Rationale:* The projector is the tested authority for date assignment incl. conflict/overflow. The endpoint calls it once, builds a `slot_id → ProjectedSlot` map, and joins it onto the existing lesson/assessment list queries (which already supply topic/chapter/status/generation fields). *Apply:* Phase 1. *Decided:* 2026-06-01 (plan).

**D-6: Group by chapter; show projected date per row; no calendar grid.** *Rationale:* Chapter grouping is already the teacher's mental model (kept from the lessons tab). Dates render as a per-row label, not a week grid — long sequential scanning across many weeks reads better as a list than a planner grid. *Apply:* Phase 2 layout. *Decided:* 2026-06-01 (plan).

**D-7: Mark exactly one "you are here" slot.** *Rationale:* The single most useful orientation cue. Reuse the existing Today-tab derivation (today's slot, else first `planned` lesson at/after today). The Today tab already computes this; the timeline highlights the same slot. *Apply:* Phase 2. The endpoint MAY return a `current` hint; if not, the frontend derives it from statuses + today's date. *Decided:* 2026-06-01 (plan).

**D-8: De-emphasise generation status.** *Rationale:* LP/exam generation state is an integration detail, not teaching content. Today every row carries a loud pill. In the timeline it becomes a quiet inline signal (small dot/label), never competing with topic + date. *Apply:* Phase 2. *Decided:* 2026-06-01 (plan).

**D-9: Surface conflict + overflow.** *Rationale:* The projector flags slots it can't place (`is_conflict`, `is_overflow`); today the UI hides them. A teacher/demo viewer should see "this assessment is anchored to a holiday" or "the plan runs past year-end". *Apply:* Phase 1 carries the flags; Phase 2 renders an inline warning on affected rows. *Decided:* 2026-06-01 (plan).

**D-10: Timeline replaces the Lessons + Assessments tabs (does not add a 3rd).** *Rationale:* Keeping three overlapping surfaces (Lessons, Assessments, Timeline) is the same fragmentation in reverse. The Timeline is the lessons+assessments surface. A `kind` filter (All / Lessons / Assessments) within the Timeline preserves single-kind browsing. *Apply:* Phase 2 removes the two tabs from `TAB_NAMES`, adds `timeline`. Today / Timetable / Book / SLOs tabs are untouched. *Decided:* 2026-06-01 (plan).

**D-11: No schema change.** *Rationale:* All data (slots, statuses, anchors, generation links) and the projector already exist. This is a read-path + UI feature. *Apply:* both phases; no migration file. *Decided:* 2026-06-01 (plan).
