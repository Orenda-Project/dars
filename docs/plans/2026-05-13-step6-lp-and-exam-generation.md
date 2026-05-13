---
type: plan
last_verified: 2026-05-13
owner: hataf
---

# Plan: Step 6 — LP & Exam Generation

## What this does

Generates actual lesson plan content and exam papers for planned slots. Two modes per type:

1. **Curriculum-linked** — generation triggered from a `ClassLessonSlot` or `AssessmentSlot`. Uses the chapter's topic content, LP type, grade, subject. Result stored back on the slot.
2. **Freehand** — teacher/client requests any LP or exam (grade, subject, topic, free text). Not tied to a chapter. Uses the existing `generated_lps/` and `generated_exams/` modules from Step 1.

## Why

Steps 1–5 build the plan. Step 6 makes the plan real — it populates each lesson slot with an actual lesson plan the teacher can open, and each assessment slot with an actual exam paper. Without this, the planner is just a calendar.

## What changes

### DB

Migration: `server/src/dars/migrations/20260513000007_lp_exam_generation.sql`

```sql
-- class_lesson_slots.lesson_plan_id should point to generated_lesson_plans (not old lesson_plans)
-- Migration in Step 1 already handles the table rename. Verify FK here:
ALTER TABLE class_lesson_slots
  DROP CONSTRAINT IF EXISTS class_lesson_slots_lesson_plan_id_fkey,
  ADD CONSTRAINT class_lesson_slots_lesson_plan_id_fkey
    FOREIGN KEY (lesson_plan_id) REFERENCES generated_lesson_plans(id) ON DELETE SET NULL;

-- assessment_slots.exam_generation_id should point to generated_exams
ALTER TABLE assessment_slots
  DROP CONSTRAINT IF EXISTS assessment_slots_exam_generation_id_fkey,
  ADD CONSTRAINT assessment_slots_exam_generation_id_fkey
    FOREIGN KEY (exam_generation_id) REFERENCES generated_exams(id) ON DELETE SET NULL;
```

### Backend — slot LP generation (`school/router.py` + `school/service.py`)

New endpoint:
- `POST /api/v1/class-lesson-slots/{id}/generate-lp` — (202 Accepted)
  - Loads slot → chapter_plan → CST (subject, grade) → chapter → topics (page ranges, topic_text)
  - Creates `GeneratedLP` row (client_id, curriculum, grade, subject, lp_type from slot, topic from slot title)
  - Queues background task: calls LP Assistant with `{curriculum, grade, subject, topic, page_content, lp_type}`
  - On complete: updates `GeneratedLP.status = READY`, sets `ClassLessonSlot.lesson_plan_id`
  - Returns: `{lesson_plan_id, status: "PENDING"}`

New endpoint:
- `POST /api/v1/chapter-plans/{id}/generate-all-lps` — (202 Accepted)
  - Queues LP generation for all `planned` slots in a chapter that don't already have an LP
  - Background task: iterates slots, calls generate per slot
  - Returns: `{queued: N, skipped: M}`

### Backend — slot exam generation (`school/router.py` + `school/service.py`)

New endpoint:
- `POST /api/v1/assessment-slots/{id}/generate-exam` — (202 Accepted)
  - Loads slot → chapter_plan → CST → chapter → topics (page ranges)
  - Creates `GeneratedExam` row (client_id, curriculum, grade, subject, page_ranges from chapter)
  - Queues background task: calls EG Assistant
  - On complete: updates `GeneratedExam.status = READY`, sets `AssessmentSlot.exam_generation_id`
  - Returns: `{exam_id, status: "PENDING"}`

### Backend — freehand (already exists from Step 1, just verify)

- `POST /api/v1/lesson-plans` — freehand LP generation (no slot linkage) ✓
- `POST /api/v1/exams` — freehand exam generation (no slot linkage) ✓

Both already implemented in Step 1. No changes needed here.

### Tests

File: `server/tests/test_slot_generation.py`
- Generate LP for slot → `GeneratedLP` created with PENDING status, slot.lesson_plan_id set
- LP completes → slot.lesson_plan_id points to READY LP
- Generate all LPs for chapter → N slots queued
- Skip slots that already have a lesson_plan_id (unless force=true)
- Generate exam for assessment slot → `GeneratedExam` created, slot.exam_generation_id set
- Client isolation: cannot generate LP for another client's slot

### Frontend

**Lesson Breakdown tab** (update from Step 5):

Each lesson slot row:
- If no LP: "Generate LP" button → spinner while PENDING → "View LP" button when READY
- "Generate All" button at chapter level → shows progress (X of N generated)
- "View LP" → slide-over panel with LP HTML content (existing `plan-window` molecule)

**Assessments tab** (update):

Each assessment slot row:
- If no exam: "Generate Exam" button → PENDING badge → "View Exam" when READY
- View Exam → slide-over with exam JSON rendered as formatted paper

**Freehand section** (new — in both dashboard and teacher app):

Dashboard sidebar: keep existing "Lesson Plans" and "Exam Generator" pages — these are freehand.
Teacher app: add "Quick LP" and "Quick Exam" buttons accessible from anywhere in the teacher app.

## Bead

- ID: `feat-step6-lp-exam-generation`
- Title: Step 6 — LP & Exam Generation
- Category: feature

## Risks & constraints

- LP generation is slow (30–120s) — must be async with status polling; never block the UI
- `page_content` for LP generation: load from chapter's topics' `topic_text` concatenated — may be long, truncate to LP Assistant limits
- EG generation uses v2 async polling internally (already implemented in `generated_exams/service.py`) — reuse this
- "Generate All" for a chapter with 10 slots fires 10 background tasks — acceptable for now, no rate limiting needed at this scale
- Webhook fires on each LP/exam completion (uses `client.webhook_url`) — ensure webhook service is called from background tasks

## E2E test scenarios

1. Chapter with 8 lesson slots → "Generate All" → all 8 queued → poll until all READY
2. Each slot's "View LP" shows correct lp_type-appropriate content
3. Assessment slot → "Generate Exam" → view exam JSON
4. Freehand LP from dashboard → works independently of chapter planning
5. Freehand exam from teacher app → works independently
6. Slot already has LP → "Generate All" skips it → count reflects correctly
