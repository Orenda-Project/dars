# Glossary — Class Timeline View

| Term | Definition |
|------|------------|
| **CST** | `ClassSubjectTeacher` — one (class × subject × teacher) assignment. The unit a timeline belongs to. Identified by `cst_id`. |
| **Timeline** | The new unified, chronological view of a CST's work: lessons + assessments interleaved by `position`, each stamped with a projected date. The deliverable of this feature. |
| **Slot** | One class period. Either a **lesson slot** (`class_lesson_slots`) or an **assessment slot** (`class_assessment_slots`). Has a global `position` (1..N) across both kinds. |
| **Position** | The global integer order of a slot within a CST, shared across lessons and assessments. Slot N is taught before slot N+1. Sequencing spine. |
| **Projected date** | The calendar date the projector assigns to a slot by walking teaching days within the academic year (skipping weekends/holidays, honouring anchors). Computed, not stored. May be `null` (overflow). |
| **Projector** | `dars.breakdown.projector.project_cst_schedule(conn, cst_id)` — returns `ProjectedSlot[]` (slot_id, slot_kind, position, projected_date, is_anchor, is_overflow, is_conflict). Already exists; this feature reuses it. |
| **Anchor date** | An admin-pinned calendar date on a slot (`anchor_date`). The projector places the slot on that date; everything else flows around it. |
| **Conflict** | Projector flag `is_conflict=True`: an anchored slot lands on a non-teaching day (holiday / weekend / outside AY). The date is recorded but the slot didn't consume a teaching day. |
| **Overflow** | Projector flag `is_overflow=True`: the CST ran out of teaching days before this slot, so `projected_date=null`. Indicates the plan exceeds the academic year. |
| **You are here / current slot** | The slot the class is currently on — the first non-`taught`/non-`skipped` lesson at or after today, or today's slot per the `/today` derivation. The timeline marks exactly one. |
| **Lesson status** | `planned` \| `taught` \| `skipped` (on `class_lesson_slots.status`). |
| **Assessment status** | `scheduled` \| `completed` \| `skipped` (on `class_assessment_slots.status`). |
| **Generation status** | LP status (`generated_lps.status`) or exam status (`generated_exams.status`): `not_generated` \| `PENDING` \| `IN_FLIGHT` \| `READY` \| `ERROR`. A secondary signal in the timeline, not primary content. |
| **Timeline item** | One row in the new endpoint's response: a discriminated union over `kind: "lesson" | "assessment"` carrying position, projected_date, status, generation status, chapter context, and topic(s). |
| **Chapter group** | Timeline items grouped by `breakdown_chapter_id`, ordered by `breakdown_chapter_position`. The primary visual grouping, preserved from today's lessons tab. |
