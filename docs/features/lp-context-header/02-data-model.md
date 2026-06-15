# Data Model — LP Context Header

**No schema changes. No migrations.** Every field this feature needs already exists in the DB (`class_lesson_slots.book_chapter_id`, `class_lesson_slots.topic_id`, `class_lesson_slots.lp_type`, `book_chapters.chapter_number`, `book_chapters.title`, `topics.title`, `topics.topic_text`). This doc records the **response-shape deltas** only (D-1).

## Source tables (ground truth, unchanged)

- `class_lesson_slots` — `id`, `cst_id`, `position`, `slot_type`, `lp_type` (nullable), `topic_id` (nullable), `book_chapter_id` (nullable), `status`, `generated_lp_id`.
- `book_chapters` — `id`, `chapter_number`, `title`.
- `topics` — `id`, `title`, `topic_text`.
- `generated_lps` — `lp_type` (not null), `topic_id`, `content`, `status`, `covered_sub_slo_ids`.

## Response deltas (Phase 1 — D-4)

### A. `GET /api/v2/today` → `LessonSlotEntry`
**Add:** `topic_title: str | None`.
Already present: `lp_type`, `topic_id`, plus chapter context lives on the sibling `current_chapter` field of `TodayEntry`. The loader (`_load_lesson_slot_full` in `router_today_calendar.py`) gets a `LEFT JOIN topics t ON t.id = cls.topic_id` to source `t.title`.

> Note: `current_chapter` (chapter_number + title) is on `TodayEntry`, not on `LessonSlotEntry`. The frontend `today-template` already has both objects in hand when rendering the lesson card, so the header can be fed chapter from `current_chapter` and topic/type from `lesson_slot`. No need to duplicate chapter onto the slot entry.

### B. `GET /api/v1/class-lesson-slots/{slot_id}` → detail dict (backs `LPViewer`)
**Add:** `chapter_number: int | None`, `chapter_title: str | None`.
Already present: `topic_id`, `topic_text`, `lp_type`. The query (`router_generation.py`) gets `LEFT JOIN book_chapters bc ON bc.id = cls.book_chapter_id` and selects `bc.chapter_number`, `bc.title AS chapter_title`. Frontend type `ClassLessonSlotDetail` in `lib/dars-api.ts` gains the two fields.

### Endpoints already context-complete (no change)
- `GET /api/v2/csts/{cst_id}/lesson-slots` → `ClassLessonSlotListItem` — has `breakdown_chapter_position`, `breakdown_chapter_title`, `topic_title`, `lp_type`. ✅
- `GET /api/v2/csts/{cst_id}/timeline` → `TimelineLessonItem` — same fields. ✅

### Out of scope (D-5)
- `GET /api/v2/me/calendar` → `LessonSlotEntry` — left as-is (lp_type + topic_id only).
- Dashboard failures list — left as-is.

## Field → label translation (Phase 2 — D-3)

Translation from raw `lp_type` to display label happens **only** on the frontend in `lpTypeLabel()`. The backend continues to send raw enum values; this is deliberate (the enum is the API contract; labels are a presentation concern).
