---
type: plan
status: draft
created: 2026-05-13
branch: feat/fk-subject-grade-curriculum
---

# FK Enforcement: subject_id, grade_id, curriculum_id

## Problem
`subject`, `grade`, `curriculum` fields across all tables are loose text/int with no FK constraints. The teacher class creation UI exposes subject as a free-text field. Grade and curriculum have the same problem.

## Goal
Every table that stores subject/grade/curriculum references a proper FK to the lookup tables.

## Column renames

| Table | Old | New | FK |
|---|---|---|---|
| `slos` | `subject TEXT` | `subject_id BIGINT` | `→ subjects(id)` |
| `slos` | `grade INTEGER` | `grade_id BIGINT` | `→ grades(id)` |
| `slos` | `curriculum TEXT` | `curriculum_id BIGINT` | `→ curriculums(id)` |
| `books` | `subject TEXT` | `subject_id BIGINT` | `→ subjects(id)` |
| `books` | `grade INTEGER` | `grade_id BIGINT` | `→ grades(id)` |
| `books` | `curriculum TEXT` | `curriculum_id BIGINT` | `→ curriculums(id)` |
| `book_chapters` | — | — | (no change, inherits from book) |
| `curriculum_chapter_schedule` | `curriculum TEXT` | `curriculum_id BIGINT` | `→ curriculums(id)` |
| `class_subject_teachers` | `subject TEXT` | `subject_id BIGINT` | `→ subjects(id)` |
| `school_classes` | `grade INTEGER` | `grade_id BIGINT` | `→ grades(id)` |
| `generated_lesson_plans` | `subject TEXT` | `subject_id BIGINT` | `→ subjects(id)` |
| `generated_lesson_plans` | `grade TEXT` | `grade_id BIGINT` | `→ grades(id)` |
| `generated_lesson_plans` | `curriculum TEXT` | `curriculum_id BIGINT` | `→ curriculums(id)` |
| `generated_exams` | `subject TEXT` | `subject_id BIGINT` | `→ subjects(id)` |
| `generated_exams` | `grade INTEGER` | `grade_id BIGINT` | `→ grades(id)` |
| `generated_exams` | `curriculum TEXT` | `curriculum_id BIGINT` | `→ curriculums(id)` |
| `clients` | `curriculum TEXT` | `curriculum_id BIGINT` | `→ curriculums(id)` |

## Files to change
- `server/src/dars/migrations/20260513000002_fk_lookups.sql` — new migration
- `server/src/dars/curriculum/models.py` — SLO, Book, CurriculumChapterSchedule
- `server/src/dars/school/models.py` — SchoolClass, ClassSubjectTeacher
- `server/src/dars/generated_lps/models.py`
- `server/src/dars/generated_exams/models.py`
- `server/src/dars/clients/models.py`
- All corresponding schemas + services that reference old column names
