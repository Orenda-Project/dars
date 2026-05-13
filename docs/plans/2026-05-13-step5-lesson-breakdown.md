---
type: plan
last_verified: 2026-05-13
owner: hataf
---

# Plan: Step 5 — Lesson Breakdown (AI Pedagogical Planning)

## What this does

Given a chapter plan (N teaching days, subject, grade, chapter content), AI decides the optimal skill-based lesson sequence: which LP types to use, in what order, and when to insert formative assessments. Supports per-chapter breakdown and whole-year breakdown. Output is a list of `ClassLessonSlot` and `AssessmentSlot` rows.

## Why

This is the core intelligence of the product. Instead of a naive cycling pattern (Reading → Grammar → Writing → repeat), the AI uses pedagogical knowledge to make genuinely useful decisions — e.g. for a poetry chapter: Read aloud → Vocabulary → Comprehension Q&A → Creative Writing → Formative Assessment → Revision. The sequence varies by subject, grade, chapter content, and available days.

## What changes

### DB

No new tables. `class_lesson_slots` and `assessment_slots` already exist and are the output of this step.

Migration: `server/src/dars/migrations/20260513000006_lesson_breakdown.sql`

```sql
-- Add lp_type to assessment_slots to distinguish formative sub-types if needed
-- (No schema change needed — assessment_type field already covers formative/summative)

-- Add index for faster slot lookup by chapter_plan_id
CREATE INDEX IF NOT EXISTS idx_class_lesson_slots_chapter_plan
  ON class_lesson_slots(chapter_plan_id);
CREATE INDEX IF NOT EXISTS idx_assessment_slots_chapter_plan
  ON assessment_slots(chapter_plan_id);
```

### Backend — `school/service.py`

Replace `generate_lesson_sequence()` with `ai_breakdown_chapter(chapter_plan_id, db)`:

**Input loaded from DB:**
- ChapterPlan: teaching_days, position
- ClassSubjectTeacher: subject, grade
- BookChapter: title, chapter_number
- Topics for this chapter: titles, page ranges, topic_text (for context)
- Academic year holidays (to be aware of gaps)

**Claude prompt structure:**
```
System: You are an expert Pakistani school curriculum planner. Given a chapter's details,
design an optimal lesson sequence using the available LP types for the subject.

LP types by subject:
- English: Reading, Vocabulary, Comprehension (Word Meanings), Comprehension (Q&A),
           Grammar, Creative Writing, Revision
- Maths: Concept Introduction, Concrete Practice, Pictorial & Abstract,
         Word Problems, Revision
- Urdu: قرأت, لغت, گرامر, تحریر, اصلاح, دہرائی
- Default: Introduction, Practice, Review, Revision

Rules:
- Last slot of a chapter is always Revision
- Insert one Formative Assessment after every 3-4 teaching days
- Never place a Formative Assessment on the first or last day
- Distribute LP types to cover chapter topics evenly

Return JSON only:
[
  {"day": 1, "type": "lesson", "lp_type": "Reading", "title": "The Clever Fox — Oral Reading"},
  {"day": 3, "type": "lesson", "lp_type": "Vocabulary", "title": "New Words from Chapter 1"},
  {"day": 5, "type": "assessment", "assessment_type": "formative", "title": "Chapter 1 FA"},
  ...
]

User: Chapter: {title}, Subject: {subject}, Grade: {grade}, Teaching days: {N}
Topics: {topic list with titles}
```

**Output processing:**
1. Parse JSON response
2. Delete existing `ClassLessonSlot` rows for this chapter_plan_id
3. Delete existing `AssessmentSlot` rows for this chapter_plan_id (formative only — leave summative)
4. Insert new rows

**`ai_breakdown_all(cst_id, db)`** — whole-year breakdown:
- Loops over all chapter plans for a CST ordered by position
- Calls `ai_breakdown_chapter()` for each
- Returns summary: {chapters_planned, total_lesson_slots, total_assessment_slots}

### Backend — router endpoints (update `school/router.py`)

Replace:
- `POST /api/v1/chapter-plans/{id}/lesson-slots/generate` — now calls `ai_breakdown_chapter()`

Add:
- `POST /api/v1/chapter-plans/{id}/lesson-slots/regenerate` — force regenerate (wipes existing, same as generate but explicit)
- `POST /api/v1/classes/{id}/subjects/{cst_id}/breakdown-year` — breakdown all chapters for a CST
  - Returns 202 Accepted (queued as background task for whole-year)
  - Body: `{status: "queued", chapters: N}`

### Tests

File: `server/tests/test_lesson_breakdown.py`
- `ai_breakdown_chapter`: mock Claude response → verify ClassLessonSlots + AssessmentSlots created
- Last slot is always Revision
- Formative assessments inserted (at least one per chapter with > 3 days)
- Regenerate wipes existing slots before re-creating
- Whole-year breakdown creates slots for all chapter plans
- Client isolation: cannot breakdown another client's chapter plan

### Frontend

**Lesson Breakdown tab** in planner (currently in `curriculum-demo/page.tsx`):

- Chapter selector dropdown
- If no slots: "Generate Lesson Breakdown" button → calls `/generate` → shows spinner
- If slots exist: timeline view showing day-by-day sequence
  - Lesson slots: day number, LP type badge (color-coded), title
  - Assessment slots: day number, "Formative Assessment" badge (amber)
  - Each slot: editable title inline, editable LP type (dropdown)
  - "Regenerate" button (with confirmation — will wipe existing)
- "Generate Whole Year" button at CST level → calls `/breakdown-year` → progress indicator

## Bead

- ID: `feat-step5-lesson-breakdown`
- Title: Step 5 — AI Lesson Breakdown
- Category: feature

## Risks & constraints

- Claude response must be valid JSON — wrap parse in try/except, fall back to simple cycling if Claude fails
- `topic_text` may be large — truncate to first 2000 chars per topic when building prompt to stay within token limits
- Whole-year breakdown is slow (one Claude call per chapter) — run as background task, not synchronous
- Urdu LP types need to be Nastaliq-friendly in the UI — use `font-nastaliq` class
- If a chapter has no topics (breakdown hasn't been run in curriculum module), still generate slots using chapter title only
- Do not wipe summative `AssessmentSlot` rows on regenerate — those are declared at the academic year level (future step)

## E2E test scenarios

1. Chapter plan with 10 teaching days → generate → 10 lesson slots + at least 2 formative assessments created
2. Last slot is always "Revision"
3. LP types are subject-appropriate (English → Reading/Grammar/etc, not Concept/Practice)
4. Regenerate → old slots gone, new slots created
5. Whole-year breakdown → all chapters get slots
6. Timeline view shows correct day numbers and type badges
7. Edit a slot title inline → saved on blur
