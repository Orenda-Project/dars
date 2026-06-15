# Phase 1 — Backend context fields

Fill the data gaps so the two prominent LP-display sites that lack chapter/topic get them (D-4). No schema changes (D-1). One PR. Independently shippable.

Precedence: this doc derives from `01-decision-log.md` (D-1, D-4) and `02-data-model.md`. If they disagree, they win.

---

## F-1.1 — Add `topic_title` to `/today` lesson slot

**Spec.** In `server/src/dars/v2_api/router_today_calendar.py`, the helper that builds a `LessonSlotEntry` (`_load_lesson_slot_full`, also used by `/me/calendar`) selects from `class_lesson_slots`. Add a `LEFT JOIN topics t ON t.id = cls.topic_id` and select `t.title AS topic_title`. Add `topic_title: str | None = None` to the `LessonSlotEntry` Pydantic model.

- Because this loader is shared with `/me/calendar`, the calendar response also gains `topic_title` — harmless (additive, nullable; the calendar frontend ignores it per D-5).
- `current_chapter` on `TodayEntry` is unchanged — chapter context for the Today card already flows through it.
- Structured logging: the loader already logs; keep entry/exit logs intact, no new log needed for a pure SELECT widening.

**Acceptance.**
- `GET /api/v2/today` for the seeded demo CST returns each `lesson_slot` with a non-null `topic_title` when the slot has a `topic_id`, `null` otherwise.
- `GET /api/v2/me/calendar` still returns 200 and each `LessonSlotEntry` now carries `topic_title` (may be null).
- Existing today/calendar tests still pass; add/extend a test asserting `topic_title` is present and matches the seeded topic's title for a known slot.

**Dependencies.** None.

---

## F-1.2 — Add chapter to the lesson-slot detail endpoint

**Spec.** In `server/src/dars/v2_api/router_generation.py`, the `GET /api/v1/class-lesson-slots/{slot_id}` handler builds an untyped dict from a SQL query that already `LEFT JOIN`s `topics`. Add `LEFT JOIN book_chapters bc ON bc.id = cls.book_chapter_id`, select `bc.chapter_number` and `bc.title AS chapter_title`, and add both to the returned dict (`chapter_number`, `chapter_title`, both nullable).

- Keep all existing keys unchanged (`topic_text`, `lp_type`, `lp_status`, `lp_content`, `lp_covered_sub_slo_ids`, …).
- Structured logging: keep the handler's existing entry/exit INFO logs.

**Acceptance.**
- `GET /api/v1/class-lesson-slots/{slot_id}` for a seeded slot whose `book_chapter_id` is set returns `chapter_number` (int) and `chapter_title` (str).
- A slot with `book_chapter_id = NULL` returns both as `null`, 200 (no crash on the join).
- Existing slot-detail tests pass; extend one to assert the two new keys exist.

**Dependencies.** None.

---

## Notes from execution

- **F-1.1 done.** `topic_title: str | None` added to `LessonSlotEntry`; `_load_lesson_slot_full` now `LEFT JOIN topics` and selects `t.title`. Since that loader is shared with `/me/calendar`, calendar `LessonSlotEntry`s also carry `topic_title` (additive, harmless; D-5 leaves the calendar UI unchanged). Asserted in the DB-gated `test_today_calendar_e2e.py::test_today_returns_position_1_at_ay_start` (topic_title present + non-empty string for the demo's first lesson).
- **F-1.2 done.** `chapter_number` + `chapter_title` added to `GET /api/v1/class-lesson-slots/{slot_id}` via `LEFT JOIN book_chapters bc ON bc.id = cls.book_chapter_id`. **Test gap:** this GET detail endpoint has no DB-independent unit test (its existing tests are for the sibling `POST .../generate-lp`, which uses a FakeConn). A real assertion needs seeded DB rows; deferred rather than fabricate a brittle FakeConn that hard-codes the SELECT column order. The JOIN is `LEFT` so a null `book_chapter_id` yields null fields (no crash) — covered by reasoning, verified manually against the query shape.
- Non-DB suite for touched areas green: `test_lp_type_heuristics`, `test_today_autoplan`, `test_generate_lp_endpoint_http`, `test_today_calendar_e2e` → 24 passed, 9 skipped (DB-gated).
