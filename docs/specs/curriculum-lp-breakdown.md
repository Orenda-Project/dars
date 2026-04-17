# Curriculum LP Breakdown

**Date:** 2026-04-17
**Status:** In progress

---

## Goal

Build the full pipeline that takes a textbook + SLO data and produces a complete queue of lesson plan stubs — one stub per LP to be generated. Generation is then triggered stub by stub (or in bulk), calling LP Assistant with topic text instead of page numbers.

---

## Full Data Model

### 1. `slo_providers`
The curriculum authority that issues SLOs (e.g. NCP, SNC Punjab). Provider-neutral from the book's perspective — the same book can be used with multiple providers.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `slug` | varchar(50) unique | e.g. `ncp` |
| `name` | varchar(255) | e.g. "National Curriculum of Pakistan (NCP)" |
| `issuing_body` | varchar(255) | e.g. "Federal Government of Pakistan" |
| `description` | text nullable | |
| `is_active` | boolean | |

### 2. `slos`
Learning outcomes issued by the provider, per grade and subject. Tied to the book implicitly through the curriculum linkage.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `provider_id` | uuid FK → slo_providers | |
| `code` | varchar(50) | e.g. `E.03.A1.01` |
| `statement` | text | |
| `grade_id` | uuid FK → grades | |
| `subject_id` | uuid FK → subjects | |
| `domain` | varchar(100) nullable | |
| `language_skills` | text[] nullable | |
| `sub_strand` | text nullable | |
| `source_id` | int nullable | Schema tool PK |
| `is_active` | boolean | |

### 3. `sub_slos`
Granular breakdown of an SLO into specific, observable skills. Authored in the Schema tool and imported into Dars.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `slo_id` | uuid FK → slos | |
| `code` | varchar(50) | e.g. `E.03.A1.01.1` |
| `statement` | text | e.g. "Identifies the main character in a story" |
| `source_id` | int nullable | Schema tool PK |
| `is_active` | boolean | |

### 4. `books`
Physical textbooks, synced from taleemabad-core. Provider-neutral.

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | from taleemabad-core |
| `title` | text | |
| `grade` | int | |
| `subject` | varchar(50) | |
| `curriculum` | varchar(20) | e.g. "ICT", "Punjab" |
| `cover_image` | text nullable | |
| `total_chapters` | int nullable | |
| `book_text` | json nullable | full text content (for topic extraction) |
| `synced_at` | timestamptz | |

### 5. `book_chapters`
| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | |
| `book_id` | int FK → books | |
| `title` | text | |
| `chapter_number` | int | |
| `start_page` | int nullable | |
| `end_page` | int nullable | |

### 6. `topics`
Atomic teaching units within a chapter. A chapter has multiple topics in sequence. This is the unit of LP generation.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `chapter_id` | int FK → book_chapters | |
| `title` | text | |
| `sequence` | int | order within chapter |
| `source_id` | int nullable | Schema tool PK |

### 7. `topic_sub_slos`
Joins topics to sub-SLOs. This is what ties book content to curriculum learning objectives.

| Column | Type | Notes |
|--------|------|-------|
| `topic_id` | uuid FK → topics | composite PK |
| `sub_slo_id` | uuid FK → sub_slos | composite PK |

### 8. `curriculums`
A named plan tying together a book, grade, subject, SLO provider, and academic year. A book is provider-neutral; the curriculum is what pins a book to a specific SLO set. The same book can have multiple curriculums for different providers or years.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `name` | varchar(255) | e.g. "Grade 3 English NCP 2025-26" |
| `grade_id` | uuid FK → grades | |
| `subject_id` | uuid FK → subjects | |
| `book_id` | int FK → books | |
| `provider_id` | uuid FK → slo_providers | |
| `academic_year` | varchar(20) | e.g. "2025-2026" |
| `is_active` | boolean | |
| `created_at` | timestamptz | |

### 9. `curriculum_topics`
Ordered list of topics within a curriculum. Topics may appear in different curriculums with different sequences.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `curriculum_id` | uuid FK → curriculums | |
| `topic_id` | uuid FK → topics | |
| `sequence` | int | order within curriculum |

### 10. `curriculum_lp_stubs`
One row per LP to be generated. The LP Breakdown Module creates these. Each stub becomes exactly one lesson plan.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `curriculum_topic_id` | uuid FK → curriculum_topics | |
| `skill_type` | varchar(50) nullable | e.g. "reading", "comprehension", "speaking", "revision" |
| `cpa_phase` | varchar(50) nullable | "concrete", "pictorial", "abstract" |
| `blooms_level` | varchar(30) nullable | "remember", "understand", "apply", "analyze", "evaluate", "create" |
| `sequence` | int | order within topic |
| `status` | varchar(20) | `pending` / `generating` / `generated` / `failed` |
| `lesson_plan_id` | uuid nullable FK → lesson_plans | set after generation |
| `created_at` | timestamptz | |

---

## Sample Rows (Grade 3 English, Chapter 1 "The Giving Tree")

```
books:               { id: 7, title: "English Grade 3", grade: 3, subject: "English", curriculum: "Punjab" }
book_chapters:       { id: 43, book_id: 7, chapter_number: 1, title: "The Giving Tree" }

topics:              { chapter_id: 43, title: "Characters and Setting", sequence: 1 }
topics:              { chapter_id: 43, title: "Themes and Morals", sequence: 2 }

slos:                { provider: NCP, code: "E.03.A1.01", statement: "Reads and understands a short story" }
sub_slos:            { slo: E.03.A1.01, code: "E.03.A1.01.1", statement: "Identifies the main character" }
sub_slos:            { slo: E.03.A1.01, code: "E.03.A1.01.2", statement: "Describes the setting" }
topic_sub_slos:      { topic: "Characters and Setting", sub_slo: "E.03.A1.01.1" }
topic_sub_slos:      { topic: "Characters and Setting", sub_slo: "E.03.A1.01.2" }

curriculums:         { name: "Grade 3 English NCP 2025-26", book_id: 7, provider: NCP, grade: G3, subject: English }
curriculum_topics:   { curriculum: above, topic: "Characters and Setting", sequence: 1 }
curriculum_topics:   { curriculum: above, topic: "Themes and Morals", sequence: 2 }

-- LP Breakdown Module produces these stubs for "Characters and Setting":
curriculum_lp_stubs: { sequence: 1, skill_type: "reading",       cpa_phase: "concrete",    blooms_level: "remember",   status: "pending" }
curriculum_lp_stubs: { sequence: 2, skill_type: "reading",       cpa_phase: "pictorial",   blooms_level: "understand", status: "pending" }
curriculum_lp_stubs: { sequence: 3, skill_type: "comprehension", cpa_phase: "abstract",    blooms_level: "apply",      status: "pending" }
curriculum_lp_stubs: { sequence: 4, skill_type: "revision",      cpa_phase: null,          blooms_level: null,         status: "pending" }
```

---

## LP Breakdown Module

An AI step that takes a curriculum topic and outputs LP stubs. Input:
- Topic title and text
- Linked sub-SLOs (statements)
- Grade, subject

Output: a list of `(skill_type, cpa_phase, blooms_level)` tuples — one per LP to generate.

The module decides the *number* and *type* of LPs needed. A reading-heavy topic may warrant 2 reading LPs + 1 comprehension + 1 revision. A maths topic might be 2 concrete + 1 pictorial + 1 abstract practice.

This is separate from LP generation — it's a planning step.

---

## LP Generation from Stubs

Once stubs exist, generation is triggered per stub. Dars calls LP Assistant with topic text instead of page numbers:

```json
{
  "curriculum": "Punjab",
  "grade": 3,
  "subject": "English",
  "topic_title": "Characters and Setting",
  "topic_text": "...",
  "sub_slos": ["Identifies the main character in a story", "Describes the setting"],
  "skill_type": "reading",
  "cpa_phase": "concrete",
  "blooms_level": "remember",
  "class_strength": 30,
  "generate_bilingual": false,
  "reasoning_enabled": true
}
```

This requires a change to the LP Assistant pipeline (`UG_LessonPlan/`) to accept `topic_text` instead of `page_number`. That is a **required dependency** for Dars to generate LPs from curriculum topics.

On success: stub `status` → `generated`, `lesson_plan_id` is set.

---

## Build Order

1. **Sub-SLOs** — schema + import pipeline from Schema tool *(migration in progress)*
2. **Topics** — new model under `book_chapters` *(migration in progress)*
3. **Topic ↔ Sub-SLO links** — `topic_sub_slos` join table *(migration in progress)*
4. **Curriculums** — named plan per grade/subject/book/provider *(migration in progress)*
5. **Curriculum Topics** — ordered topic list per curriculum *(migration in progress)*
6. **LP Breakdown Module** — AI step producing LP stubs from a topic
7. **LP Assistant update** — accept `topic_text` instead of `page_number`
8. **Stub generation** — trigger LP generation per stub, track status, set `lesson_plan_id`

---

## Current State

| Component | Status |
|-----------|--------|
| SLO providers + SLOs (NCP) | Done — imported to DB |
| Books + chapters | Done — synced from taleemabad-core |
| Sub-SLOs | In progress — migration `20260414000002` |
| Topics | In progress — migration `20260414000002` |
| Topic ↔ Sub-SLO links | In progress — migration `20260414000002` |
| Curriculums | In progress — migration `20260414000002` |
| Curriculum topics | In progress — migration `20260414000002` |
| Curriculum LP stubs | In progress — migration `20260414000002` |
| LP Breakdown Module | Not built |
| LP Assistant topic-text mode | Not built (UG_LessonPlan change required) |
| Stub generation trigger | Not built |

---

## Out of Scope (Phase 1)

- Continuity enforcement across LPs (carrying forward context from LP n to LP n+1)
- SNC/Punjab SLO import (NCP only for now)
- Bulk curriculum generation UI
