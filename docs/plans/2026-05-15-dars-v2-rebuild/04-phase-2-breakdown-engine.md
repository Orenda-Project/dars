# Phase 2: Breakdown Engine

**Goal:** Port Schema's breakdown logic into dars. Implement breakdown CRUD with global/org/class scope, fork semantics, sequence-only projection with anchors, three-level holiday inheritance, and a full Dars Curriculum English G1 global breakdown published.

**Bead:** `feat-v2-phase-2-breakdown`. Open at start, close on staging green.

**Pre-reqs:** Phase 1 complete on staging.

**Deliverables:**
- Schema modules ported into `dars/server/src/dars/breakdown/`
- Breakdown CRUD endpoints (global, org, class scope)
- Fork endpoint (copy parent into a new breakdown with new scope)
- Sequence-to-calendar projector with anchor + holiday awareness
- Class-level realization: when a Class's breakdown is published, ClassLessonSlots and ClassAssessmentSlots are created
- Mark-taught + SlotProgress event log + sub-SLO coverage updates
- Mid-year onboarding endpoint (declarative position)
- A published global breakdown for Dars Curriculum English G1, derived from the seed
- Demo Org has forked the global into an org-level breakdown
- Demo class has forked the org-level into a class breakdown, with slots realized

**NOT in this phase:** LP/Exam generation, FE changes, dashboard breakdown editor (that's Phase 5).

---

## Feature order

1. **F2.1** — Port Schema's `slo_breakdown.py` into `dars/breakdown/slo_breakdown_service.py`
2. **F2.2** — Port Schema's `chapter_plan.py` into `dars/breakdown/chapter_breakdown_service.py`
3. **F2.3** — Port Schema's prompts into `dars/breakdown/prompts/`
4. **F2.4** — Breakdown CRUD endpoints (global scope)
5. **F2.5** — Auto-build breakdown from book + curriculum (deterministic + LLM-assisted)
6. **F2.6** — Sub-SLO breakdown trigger endpoint (manual + during seed)
7. **F2.7** — Fork endpoints: org-fork-from-global, class-fork-from-org
8. **F2.8** — Sequence-to-calendar projector
9. **F2.9** — Class realization: instantiate ClassLessonSlots from a Breakdown
10. **F2.10** — Holiday inheritance (Org → School → CST)
11. **F2.11** — Anchor placement and conflict detection
12. **F2.12** — Mark-taught flow + SlotProgress + sub-SLO coverage
13. **F2.13** — Mid-year onboarding endpoint
14. **F2.14** — Run breakdown generation on seed; publish to staging
15. **F2.15** — Today endpoint rewrite (uses new breakdown projection)
16. **F2.16** — Calendar endpoint rewrite (same projector)

---

## F2.1 — Port `slo_breakdown.py`

**Motivation:** Schema's `run_breakdown(grade, subject)` generates sub-SLOs from SLOs using GPT-4o/Claude. We need this in dars to support the eager + on-demand sub-SLO generation per D-3.

**Spec:**
- Source: [../../../../Schema/services/slo_breakdown.py](../../../../Schema/services/slo_breakdown.py) lines 138–203
- Destination: `server/src/dars/breakdown/slo_breakdown_service.py`
- Port from sync Flask to async FastAPI:
  - Convert sync `_call_llm()` to async using `httpx.AsyncClient`
  - Use dars's existing LLM credentials (env vars: `OPENROUTER_API_KEY`, etc.)
  - Replace Schema's `output/{subject}/{grade}.json` file cache with DB writes to `sub_slos` table
- Input: list of SLO IDs to break down
- Output: list of sub-SLO records (created in DB)
- Idempotent: if a sub-SLO with `source='schema_breakdown'` already exists for an SLO, skip unless `force=True`
- Logs at INFO entry/exit per Critical Rule #11

**Test plan:**
- Unit test: mock LLM response; verify sub-SLO records inserted matching the structure
- Integration test: run against a small SLO subset on staging; verify shape

**Acceptance:**
- Module compiles and runs against staging
- Inserted sub-SLOs match the schema (parent SLO FK, valid statement, position)

---

## F2.2 — Port `chapter_plan.py`

**Motivation:** Schema's chapter-plan generates topic boundaries + day-wise plan. We need it for: (a) drafting topics from OCR'd chapters (D-4 hybrid), (b) generating the slot sequence for a breakdown.

**Spec:**
- Source: [../../../../Schema/services/chapter_plan.py](../../../../Schema/services/chapter_plan.py) (especially `_breakdown_chapter_topics()` and `map_topics_to_ncp_slos()`)
- Destination: `server/src/dars/breakdown/chapter_breakdown_service.py`
- Two functions:
  - `extract_topics_from_chapter(book_chapter_id) -> list[TopicDraft]`: reads `chapter_text`, calls LLM with `topic_breakdown_prompt`, parses output, returns drafts (does NOT insert until admin publishes)
  - `map_topics_to_sub_slos(topic_ids, sub_slo_ids) -> list[(topic_id, sub_slo_id)]`: maps topics to sub-SLOs via LLM
- Topic drafts saved to `topics` table with `status='draft'`. Admin publish flow flips to `status='published'`.

**Test plan:**
- Mock LLM; verify draft topics inserted with `status='draft'`
- Verify topic-to-sub-SLO mappings populated in `topic_sub_slos`

**Acceptance:** module compiles, can be invoked from admin flow.

---

## F2.3 — Port Schema prompts

**Motivation:** Schema's prompts are LLM-agnostic text files; clone them verbatim.

**Spec:**
- Source: [../../../../Schema/prompts/](../../../../Schema/prompts/) (all `*.txt`)
- Destination: `server/src/dars/breakdown/prompts/`
- Files to copy:
  - `topic_breakdown_prompt.txt` (chapter → topic extraction)
  - `chapter_plan_prompt.txt` (topics → day-wise plan)
  - `mapping_prompt.txt` (textbook → SLO)
  - `lp_tagging_prompt.txt` (LP → SLO tagging — used in Phase 3)
  - `math_prompt.txt`, `english_prompt.txt`, `urdu_prompt.txt` (subject-specific SLO breakdown)
- Load via `prompt_store.py` (also ported) — a simple `get_prompt(name)` function that reads the .txt file
- For dars: don't replicate Schema's DB-backed prompt storage; just use the .txt files in the repo. Simpler.

**Test plan:** verify each prompt file is present and `get_prompt('topic_breakdown')` returns the expected string.

**Acceptance:** all prompts available; no LLM call yet (later features use them).

---

## F2.4 — Breakdown CRUD endpoints (global scope)

**Motivation:** Admin needs to author the global Dars Curriculum English G1 breakdown.

**Spec:**

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/breakdowns` | Create a new breakdown (scope, curriculum, grade, subject, book, status='draft') |
| GET | `/api/v1/breakdowns` | List breakdowns (filter by `?scope=`, `?curriculum_id=`, `?grade_id=`, `?subject_id=`, `?status=`) |
| GET | `/api/v1/breakdowns/{id}` | Single breakdown (includes chapters + slots, deeply expanded) |
| PATCH | `/api/v1/breakdowns/{id}` | Edit (only allowed on draft; creates a new version with `previous_version_id` per D-18) |
| POST | `/api/v1/breakdowns/{id}/publish` | Publish: flips status to `published`, creates a new immutable record |
| DELETE | `/api/v1/breakdowns/{id}` | Soft-delete a draft (cannot delete published) |
| POST | `/api/v1/breakdowns/{id}/chapters` | Add a chapter to a draft breakdown |
| PATCH | `/api/v1/breakdowns/{id}/chapters/{chapter_id}` | Edit teaching_days, position |
| POST | `/api/v1/breakdowns/{id}/slots` | Add a slot (lesson/assessment/revision) |
| PATCH | `/api/v1/breakdowns/{id}/slots/{slot_id}` | Edit a slot |
| DELETE | `/api/v1/breakdowns/{id}/slots/{slot_id}` | Remove a slot from a draft |

For global breakdowns, only Dars-internal users author them (no org-scoped). For v1, the seed creates the global breakdown directly; the admin CRUD UI is for editing it later.

**Auth model:** global breakdown CRUD is admin-only. Use a simple `?admin_token=` query param backed by env var for v1 (no proper admin user model yet); harden in v2.

**Validation rules:**
- `lp_type` MUST be in the valid set per subject (see glossary)
- Published breakdowns are immutable; PATCH on published returns 409
- `slot.topic_id` must exist and belong to a chapter in the breakdown
- `slot.anchor_date` (if set) must fall within the academic year (only validated when realized to a CST; global breakdowns can have anchors that resolve later)

**Test plan:**
- Create draft → add chapters → add slots → publish; assert state transitions
- Try to PATCH a published breakdown → 409
- Try to add a slot with invalid lp_type for the subject → 422

**Acceptance:** all endpoints documented; tests passing.

---

## F2.5 — Auto-build breakdown from book + curriculum

**Motivation:** Authoring a breakdown slot-by-slot is tedious. The breakdown engine should propose a draft from a book + day budget.

**Spec:**
- Endpoint: `POST /api/v1/breakdowns/auto-build`
- Body: `{ curriculum_id, grade_id, subject_id, book_id, total_teaching_days: 180, fa_cadence: 5, sa_per_chapter: 1 }`
- Logic:
  1. Compute per-chapter day budget proportionally (or via LLM if `mode='ai'` query param)
  2. For each chapter, generate slot sequence:
     - For each topic in chapter, emit 1-2 lesson slots (based on topic length + sub-SLO count)
     - Pick `lp_type` based on topic type heuristic (e.g. reading passage → `reading`, grammar topic → `grammar`)
     - Every K slots, emit an FA slot covering the recent topics
     - At chapter end, emit an SA slot covering all topics in the chapter
     - Last slot in chapter = revision
  3. Save as a draft breakdown
- For Dars Curriculum English G1: this builds the v1 global breakdown automatically from the seed (D-15, D-28).

**Test plan:**
- Auto-build against seed → verify draft breakdown has reasonable structure (10 chapters, ~150-180 slots total, mix of lesson + FA + SA + revision)
- Verify all `lp_type` values are valid per subject

**Acceptance:** running auto-build on Dars Curriculum English G1 produces a publishable draft.

---

## F2.6 — Sub-SLO breakdown trigger endpoint

**Motivation:** Manual trigger per D-3 — admin clicks "break down SLOs" or it runs during seed.

**Spec:**
- Endpoint: `POST /api/v1/slos/{slo_id}/breakdown` → triggers `slo_breakdown_service.run_breakdown()` for that SLO
- Endpoint: `POST /api/v1/breakdowns/sub-slos/bulk` body `{ slo_ids: [...] }` → batch trigger
- Idempotent: if sub-SLOs already exist with `source='schema_breakdown'`, return existing unless `force=true`
- Async (FastAPI BackgroundTasks per D-42) for bulk; sync for single SLO
- During seed: F1.3 creates manual sub-SLOs. Later, admin can call this to add machine-generated sub-SLOs as additional ones.

**Test plan:**
- POST single → assert sub-SLOs added with source=schema_breakdown
- POST bulk → assert all SLOs processed; returns counts

**Acceptance:** endpoint works; manual seed sub-SLOs are not duplicated.

---

## F2.7 — Fork endpoints

**Motivation:** Org admins fork the global breakdown for their org; teachers fork the org breakdown for their class.

**Spec:**

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/breakdowns/{global_id}/fork-org` | Org admin forks global → org-scope draft |
| POST | `/api/v1/breakdowns/{org_id}/fork-class` | Org admin (acting for teacher) forks org → class-scope draft for a specific CST |

Body for fork-org: `{ org_id }` (the calling org).  
Body for fork-class: `{ cst_id }`.

Fork logic (D-3):
1. Deep-copy the parent breakdown row + all `breakdown_chapters` + all `breakdown_slots` + all `breakdown_slot_topics`
2. New breakdown has `parent_breakdown_id` = source; `scope` = `org` or `class`; `scope_ref_id` = org_id or cst_id; `status='draft'`
3. Return the new breakdown

Once forked, admin (for org) or teacher-via-org (for class) can edit through standard CRUD endpoints.

**Constraints:**
- Org can only have one breakdown per `(curriculum, grade, subject)`. If one exists in draft, return 409 ("you already have a draft"); in published, allow creating a new draft that becomes a version.
- Same constraint for class.

**Test plan:**
- Fork global → org; verify deep copy
- Edit one slot in org breakdown; verify parent global is unchanged
- Fork org → class; verify deep copy
- Attempt to fork-org with no global published yet → 404
- Attempt to fork-org twice without first publishing → 409

**Acceptance:** test cases pass.

---

## F2.8 — Sequence-to-calendar projector

**Motivation:** Slots have sequence positions, not dates. The projector turns a CST's slots into calendar dates by walking teaching days.

**Spec:**
- Service: `dars/breakdown/projector.py`
- Function: `project_cst_schedule(cst_id, db) -> list[ProjectedSlot]`
- ProjectedSlot = `{ slot_id, slot_kind: 'lesson'|'assessment', position, projected_date, is_anchor }`
- Logic:
  1. Load CST → academic year start/end
  2. Compute teaching days: walk start..end, skip non-timetable days, skip holidays (use F2.10 holiday computation)
  3. Load all slots (class_lesson_slots + class_assessment_slots) for the CST, ordered by position
  4. Walk slots and teaching days together:
     - If slot has `anchor_date`: skip teaching days until we hit `anchor_date`. If we run out of days before the anchor, mark the slot `is_overflow=True`. If anchor falls on a non-teaching day, flag as conflict.
     - Else: assign current teaching day; advance
  5. Return ordered list

**Test plan:**
- Mock CST with 100 teaching days, 100 slots, no anchors → projected_dates are sequential teaching days
- Same, but slot 50 has anchor on a specific date → slots 1..49 fill before; slot 50 anchored; 51+ continue after
- Anchor falls on a holiday → returns conflict

**Acceptance:** projector handles holidays, anchors, and basic conflicts correctly.

---

## F2.9 — Class realization: instantiate slots from a Breakdown

**Motivation:** When a class breakdown is published, the planning rows in `breakdown_slots` must materialize as `class_lesson_slots` and `class_assessment_slots` for that CST.

**Spec:**
- Endpoint: `POST /api/v1/breakdowns/{class_breakdown_id}/realize` (called by publish flow internally; also exposed for re-realize)
- Logic:
  1. For each `breakdown_slot` in the class breakdown (ordered by position):
     - If `slot_type='lesson'` or `'revision'`: insert `class_lesson_slots` row with copied fields, status='planned'
     - If `slot_type='formative_assessment'` or `'summative_assessment'`: insert `class_assessment_slots` row with copied fields, status='scheduled', then insert `class_assessment_slot_topics` from `breakdown_slot_topics`
  2. Existing slots for the CST are not deleted — re-realize is idempotent on `(cst_id, position)` via UNIQUE; failed inserts mean position already exists and we update instead

**Test plan:**
- Realize a class breakdown → assert ClassLessonSlot and ClassAssessmentSlot rows created with correct counts
- Re-realize → no duplicates
- Verify lesson slot count matches breakdown's lesson count

**Acceptance:** realization is idempotent and creates the right slot types.

---

## F2.10 — Holiday inheritance

**Motivation:** D-26 specifies Org → School → CST holiday inheritance. Projector needs the resolved set.

**Spec:**
- Service: `dars/breakdown/holidays.py`
- Function: `get_effective_holidays(cst_id, academic_year_id, db) -> set[date]`
- Logic:
  1. Start with empty set
  2. Add all `org_holidays` for the AY
  3. Apply `school_holiday_overrides`: if `action='add'`, add date; if `action='remove'`, remove date
  4. Apply `cst_holiday_overrides`: same
  5. Return final set
- Endpoints:
  - `GET /api/v1/orgs/me/holidays?academic_year_id=...` → list org-level
  - `GET /api/v1/schools/{id}/holidays` → list effective (org + school overrides)
  - `GET /api/v1/csts/{id}/holidays` → list effective (full inheritance)
  - `POST /api/v1/orgs/me/holidays` → add org-level holiday
  - `POST /api/v1/schools/{id}/holiday-overrides` → add school override
  - `POST /api/v1/csts/{id}/holiday-overrides` → add CST override (teacher sick day)

**Test plan:**
- Org has 3 holidays; school removes 1; CST adds 2 personal → effective set = (3 - 1) + 2 = 4

**Acceptance:** correct set math at all 3 levels.

---

## F2.11 — Anchor placement and conflict detection

**Motivation:** D-7 — admins can anchor slots (e.g. "final exam on May 30").

**Spec:**
- Endpoint: `PATCH /api/v1/breakdowns/{id}/slots/{slot_id}/anchor` body `{ anchor_date: '2026-05-30' | null }`
- Validation:
  - Only allowed on global or org scope (D-7: teachers cannot anchor)
  - Anchor must be in the future relative to publish-time? **No** — anchors are intentions; projector handles past-anchor by flagging
- When projecting, the projector detects conflicts:
  - Slot can't fit before its anchor (too few teaching days)
  - Anchor falls on a holiday or non-timetable day
- Return projector's `is_overflow` and `is_conflict` flags in any endpoint that projects (today, calendar)

**Test plan:**
- Anchor a slot 10 teaching days before its natural sequence position → projector compresses
- Anchor a slot 10 days after its natural position → projector inserts gap
- Anchor on a holiday → conflict flag raised

**Acceptance:** projector exposes conflicts; admin dashboard (Phase 5) will surface them.

---

## F2.12 — Mark-taught flow + SlotProgress + sub-SLO coverage

**Motivation:** Core teacher action. Triggers sub-SLO coverage updates.

**Spec:**
- Endpoint: `POST /api/v1/class-lesson-slots/{slot_id}/mark-taught` body `{ taught_on?: 'YYYY-MM-DD' (default today) }`
- Endpoint: `POST /api/v1/class-lesson-slots/{slot_id}/skip` body `{ reason?: 'string' }`
- Endpoint: `POST /api/v1/class-assessment-slots/{slot_id}/complete` body `{ taught_on?: 'YYYY-MM-DD' }`
- All three:
  1. Insert `slot_progress` row
  2. Update slot's `status` column (denormalized for fast reads)
  3. If `taught` on a lesson slot: for each sub-SLO linked to the slot's topic, upsert `cst_sub_slo_coverage` to `status='taught', marked_at=NOW()` (D-5)
  4. Recompute `cst_state.current_sequence_position` = max(position of any slot with action='taught' or 'completed' or 'skipped') + 1
- Out-of-order completion is allowed (D-11). Gaps are preserved.

**Endpoint:** `GET /api/v1/csts/{id}/sub-slo-coverage` → returns map sub_slo_id → status (taught/not_taught), used in reports.

**Test plan:**
- Mark slot taught → sub-SLO coverage updated; sequence advanced
- Skip Day 2 by marking Day 3 directly → Day 2 stays not-taught; position = 4
- Mark Day 2 later → it taught; position recomputed (still 4, because Day 3 already taught)

**Acceptance:** event log accurate; coverage and position consistent.

---

## F2.13 — Mid-year onboarding endpoint

**Motivation:** Teachers arrive mid-year and declare their position (D-12).

**Spec:**
- Endpoint: `POST /api/v1/csts/{id}/onboard` body `{ chapter_position: 3, chapter_day: 5 }` (where chapter_position is the breakdown's chapter position, chapter_day is the day within that chapter)
- Logic:
  1. Resolve chapter_position to the breakdown's chapter
  2. Find slot in that chapter at chapter_day → its global `position`
  3. Set `cst_state.current_sequence_position = that_position`
  4. Set `cst_state.joined_at_position = that_position`
  5. Slots before joined_at_position remain unmarked (`status='planned'`, no SlotProgress event) → SLO coverage report shows them as "unknown" (D-12)

**Test plan:**
- Onboard CST at chapter 3, day 5 → position computed correctly
- Coverage report shows pre-position slots as unknown, not "not_taught"

**Acceptance:** flag in coverage UI distinguishes "unknown" from "not_taught."

---

## F2.14 — Run breakdown generation on seed; publish to staging

**Motivation:** Walk the talk. The seed produces a published global + forked org + forked class breakdown so the rest of dars has live data to query.

**Spec:**
- Extend `v2_seed.py`:
  1. Call `POST /api/v1/breakdowns/auto-build` with Dars Curriculum, G1, Eng, the seed book → draft global
  2. Manually adjust slot count to ~180 days (configurable)
  3. Publish the global
  4. Fork into org-scope for Demo Org → draft
  5. Publish the org breakdown
  6. Fork into class-scope for the Demo Class CST → draft
  7. Publish the class breakdown → triggers realization → ClassLessonSlots + ClassAssessmentSlots created

**Test plan:**
- After seed: `GET /api/v1/csts/{demo_cst_id}/lesson-slots` returns ~160 lesson slots
- `GET /api/v1/csts/{demo_cst_id}/assessment-slots` returns ~20 assessment slots (12 FA + 10 SA + revisions counted as lesson)
- All slot positions are contiguous 1..N

**Acceptance:** seed produces a fully-realized class with slots ready for generation in Phase 3.

---

## F2.15 — Today endpoint rewrite

**Motivation:** Replace the buggy /today (we already partially fixed it). Now use the breakdown projector.

**Spec:**
- Endpoint: `GET /api/v1/today` (replaces existing)
- Returns: list of `TodaySlotEntry` per CST owned by the org's default teacher
  - Resolved as: for each of the teacher's CSTs, project the schedule, find the slot whose `projected_date == today`
  - If today is an assessment slot: return assessment fields populated
  - Else if today is a lesson slot: return lesson fields populated
  - Plus previous taught lesson for context
  - Includes `subject` (string), `day_number` (= slot's position), `assessment_slot` if applicable
- Empty array if today is non-teaching for all CSTs

**Test plan:**
- Mock CST with today projected to slot position 5; assert response returns that slot
- Mock CST where today is a holiday (no slot projected) → CST excluded
- Mock CST with anchored FA on today → assessment_slot returned, no lesson_slot

**Acceptance:** today endpoint matches calendar projection exactly; no more divergence.

---

## F2.16 — Calendar endpoint rewrite

**Motivation:** Same projector backs the calendar.

**Spec:**
- Endpoint: `GET /api/v1/me/calendar?week_start=YYYY-MM-DD`
- Returns: list of days Mon-Fri with projected slots for each (mix of lessons and assessments)
- Uses the same projector as today; consistency guaranteed by construction

**Test plan:** projector is exercised; today's column matches what `/today` returns for the same date.

**Acceptance:** calendar and today always agree.

---

## Phase 2 wrap-up checklist

- [ ] Schema modules ported and tested
- [ ] Breakdown CRUD endpoints working
- [ ] Fork flow: global → org → class produces correct deep copies
- [ ] Projector handles holidays, anchors, conflicts
- [ ] Realization creates correct slot counts per CST
- [ ] Mark-taught updates SlotProgress + sub-SLO coverage + cst_state position
- [ ] Mid-year onboarding sets position correctly
- [ ] Seed produces published global + org + class breakdown with realized slots
- [ ] Today + calendar use the same projector; no divergence
- [ ] Staging deployed; manual smoke test green

Open Phase 3 bead.
