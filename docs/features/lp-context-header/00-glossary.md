# Glossary — LP Context Header

Future docs may only use terms defined here. Add new terms as they emerge.

| Term | Definition |
|---|---|
| **LP** | Lesson Plan. The generated teaching artifact for one lesson slot. |
| **LP type** (`lp_type`) | The kind of lesson, a subject-specific enum stored on `class_lesson_slots.lp_type` and `generated_lps.lp_type`. Values per subject defined in `server/src/dars/breakdown/planner_models.py` `VALID_LP_TYPES`. E.g. Eng/Urdu: `reading`, `comprehension_word_meanings`, `comprehension_qa`, `grammar`, `creative_writing`, `revision`. Maths: `concrete`, `pictorial_and_abstract`, `word_problems`, `revision`. Other subjects: `revision`. Nullable in some response shapes. |
| **Chapter** | The book chapter an LP slot belongs to, via `class_lesson_slots.book_chapter_id` → `book_chapters` (`chapter_number`, `title`). |
| **Topic** | The specific topic an LP covers, via `class_lesson_slots.topic_id` → `topics` (`title` short label, `topic_text` longer prose). |
| **LP display site** | Any UI location that renders an LP or an LP slot to a user. The eight sites are enumerated in the phase-2 doc. Examples: Today card, syllabus/timeline rows, LP slide-over, calendar cells. |
| **LP Context Header** | The new shared frontend presentation introduced by this feature: **topic title (headline) + chapter (eyebrow above) + LP-type badge** (D-2). Implemented as a `molecules/lp-context-header.tsx` component. |
| **`lpTypeLabel()`** | The single frontend helper (in `lib/`) that maps a raw `lp_type` enum value to a human-readable label (D-3). The one place raw enum strings are translated for display. |
| **LP-type badge** | A colored pill rendering the `lpTypeLabel()` of the type, following the existing badge pattern (`rounded-full`, terra background, `text-[11px] font-semibold`) seen in `reteach-panel.tsx`. |
| **Eyebrow** | A small uppercase, letter-spaced, muted line above a headline — existing Dars pattern (`text-[10px]/text-xs uppercase tracking-wide text-dars-muted`). Used here for the chapter line. |
| **Context-complete endpoint** | An LP-returning endpoint whose response carries chapter (number + title) **and** topic (title) **and** lp_type together. `/csts/{id}/lesson-slots` and `/csts/{id}/timeline` already are; this feature makes the rest so where it matters (D-4). |
| **Syllabus (teacher-app)** | The `?tab=syllabus` view of `/teacher-app/classes/[cst_id]` — lists the class's chapters (each a `ClassPathChapter`). Currently expands a chapter inline; this feature replaces that with navigation to the Chapter Page (D-8). |
| **Chapter Page** | New dedicated teacher-app route `/teacher-app/classes/[cst_id]/chapters/[position]` showing one chapter's full detail (its lesson + assessment slots) with a back link to the syllabus. Self-fetching client component (D-10), keyed by chapter `position` (D-9). |
| **`position`** | The chapter's ordinal in the class path. Stable join key between `ClassPathChapter.position` (syllabus) and `TimelineLessonItem.breakdown_chapter_position` (timeline). The Chapter Page's URL param (D-9). |
| **`ChapterContents`** | Existing component (`class-syllabus-tab.tsx`) that renders a chapter's lesson + assessment slot rows. Reused by the Chapter Page (D-11). |
| **`PathRow`** | Existing syllabus chapter-row component. Loses its accordion toggle; becomes a `Link` to the Chapter Page (D-11). |
