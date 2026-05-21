# Data Model

Final schema for Dars v2. All tables, columns, indexes, FKs, plus migration SQL.

**Important conventions** (from `dars/docs/conventions.md` + Critical Rule #6):
- UUID primary keys via `sqlalchemy.types.Uuid` (NOT `dialects.postgresql.UUID` — breaks SQLite tests). All v2 PKs are UUID; no legacy BIGSERIAL+UUID dual pattern (**D-62**).
- `created_at`, `updated_at` on every table
- All multi-tenant tables filter by `org_id` in queries
- Migrations live in `server/src/dars/migrations/` as plain SQL (not Alembic)

**Application-level invariants not enforced by the DB:**
- `breakdowns.book_id` is required for every scope in v1 (**D-69**). The column is nullable in the schema (forward compat) but the service layer rejects inserts without it.
- `class_lesson_slots.status` and `class_assessment_slots.status` are materialized columns updated synchronously by the mark-taught flow (**D-67**). Don't compute them at read time.
- Mark-taught is one DB transaction that updates BOTH `slot_progress` (event log) AND `<slot>.status` (denorm) — never one without the other (**D-70**).

---

## Section 1: Tenancy

### `organizations`
Top-level tenant. Replaces legacy `clients`.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `name` | TEXT | "Lahore Schools Network" |
| `curriculum_id` | UUID FK → `curriculums.id` | The ONE curriculum this org uses (D-25) |
| `api_key_hash` | TEXT | SHA-256, shown once at creation |
| `api_key_prefix` | TEXT | First 8 chars for display, e.g. `dk_test_a1b2` |
| `default_teacher_id` | UUID FK → `teachers.id` NULL | The teacher to use in the sample teacher app |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

### `org_admins`
Humans who log into the dashboard.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK → `organizations.id` | |
| `email` | TEXT UNIQUE | |
| `password_hash` | TEXT | bcrypt |
| `name` | TEXT | |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

### `schools`
A school under an Org.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK → `organizations.id` | |
| `name` | TEXT | "Lahore Branch — Defence" |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

### `teachers`
A teacher belongs to a school.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK → `organizations.id` | denormalized for tenancy queries |
| `school_id` | UUID FK → `schools.id` | |
| `name` | TEXT | |
| `email` | TEXT NULL | optional; teacher app is auth-free |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

### `academic_years`
Per school. (Note: re-scoped from current per-org to per-school.)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK → `organizations.id` | denorm |
| `school_id` | UUID FK → `schools.id` | |
| `name` | TEXT | "2026–2027" |
| `start_date` | DATE | |
| `end_date` | DATE | |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

### `school_classes`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK | denorm |
| `school_id` | UUID FK | |
| `academic_year_id` | UUID FK → `academic_years.id` | |
| `grade_id` | UUID FK → `grades.id` | |
| `section` | TEXT | "A", "B" |
| `name` | TEXT | derived: e.g. "Grade 1 - A" |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

### `class_subject_teachers` (CST)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK | denorm |
| `school_class_id` | UUID FK → `school_classes.id` | |
| `subject_id` | UUID FK → `subjects.id` | |
| `teacher_id` | UUID FK → `teachers.id` NULL | nullable if unassigned |
| `book_id` | UUID FK → `books.id` NULL | one book per CST (D-13) |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

UNIQUE `(school_class_id, subject_id)` — one CST per class+subject.

### `cst_state`
Per-CST runtime state (D-60).

| Column | Type | Notes |
|---|---|---|
| `cst_id` | UUID PK FK → `class_subject_teachers.id` | |
| `current_sequence_position` | INT NOT NULL DEFAULT 1 | next slot to teach |
| `joined_at_position` | INT NOT NULL DEFAULT 1 | mid-year onboarding |
| `last_marked_at` | TIMESTAMPTZ NULL | |
| `updated_at` | TIMESTAMPTZ | |

---

## Section 2: Curriculum

### `curriculums`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `code` | TEXT UNIQUE | "DARS", "NCP", "SNC" |
| `name` | TEXT | "Dars Curriculum" |
| `description` | TEXT | |
| `is_active` | BOOL DEFAULT TRUE | |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

### `grades`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `code` | INT UNIQUE | 1..12 |
| `display_name` | TEXT | "Grade 1" |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

### `subjects`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `code` | TEXT UNIQUE | "Eng", "Urdu", "Maths", "Science", "GK", "Islamiat", "GenSci", "SST" |
| `display_name` | TEXT | "English" |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

### `slos`
Curriculum-level SLOs.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `curriculum_id` | UUID FK → `curriculums.id` | |
| `grade_id` | UUID FK → `grades.id` | |
| `subject_id` | UUID FK → `subjects.id` | |
| `code` | TEXT | "A1-02" |
| `statement` | TEXT | "Student can read CVC words" |
| `domain` | TEXT NULL | Bloom's, optional |
| `position` | INT | display order |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

UNIQUE `(curriculum_id, grade_id, subject_id, code)`.

### `sub_slos`
LLM-broken-down granular outcomes.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `slo_id` | UUID FK → `slos.id` | |
| `code` | TEXT | "A1-02-a" (suffix) |
| `statement` | TEXT | granular: "Student can identify CVC words in isolation" |
| `position` | INT | order within parent SLO |
| `source` | TEXT | "manual" \| "schema_breakdown" |
| `recommended_lp_type` | TEXT NULL | per-sub-SLO lp_type override; if set, wins over parent SLO's `recommended_lp_type` (see `breakdown/lp_type_heuristics.py`). Populated by the NCP seed; NULL for existing Dars sub-SLOs (which inherit parent's value). Added by migration `20260520000002_sub_slos_add_recommended_lp_type.sql`. Allowed values validated in application code, not the DB. |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

UNIQUE `(slo_id, code)`.

---

## Section 3: Books

### `books`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `curriculum_id` | UUID FK | |
| `grade_id` | UUID FK | |
| `subject_id` | UUID FK | |
| `title` | TEXT | |
| `publisher` | TEXT NULL | |
| `edition` | TEXT NULL | |
| `published_year` | INT NULL | |
| `total_chapters` | INT NULL | |
| `pdf_url` | TEXT NULL | |
| `book_text` | JSONB NULL | `[{pdf_page_no, text}, ...]` |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

### `book_chapters`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `book_id` | UUID FK → `books.id` | |
| `chapter_number` | INT | 1, 2, 3... |
| `title` | TEXT | |
| `start_page` | INT NULL | |
| `end_page` | INT NULL | |
| `chapter_text` | JSONB NULL | OCR slice for this chapter |
| `status` | TEXT DEFAULT 'draft' | `draft \| published` (D-4) |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

UNIQUE `(book_id, chapter_number)`.

### `topics`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `book_chapter_id` | UUID FK → `book_chapters.id` | |
| `topic_number` | INT | 1, 2, 3 within chapter |
| `title` | TEXT | |
| `start_line` | INT NULL | line in `chapter_text` |
| `end_line` | INT NULL | |
| `topic_text` | TEXT NULL | the OCR slice (concatenated) |
| `status` | TEXT DEFAULT 'draft' | (D-4) |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

UNIQUE `(book_chapter_id, topic_number)`.

### `book_chapter_slos`
Many-to-many: chapter ↔ SLO.

| Column | Type | Notes |
|---|---|---|
| `book_chapter_id` | UUID FK | |
| `slo_id` | UUID FK | |
| PK `(book_chapter_id, slo_id)` | | |

### `topic_sub_slos`
Many-to-many: topic ↔ sub-SLO.

| Column | Type | Notes |
|---|---|---|
| `topic_id` | UUID FK | |
| `sub_slo_id` | UUID FK | |
| PK `(topic_id, sub_slo_id)` | | |

---

## Section 4: Breakdown

### `breakdowns`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `scope` | TEXT NOT NULL | `global \| org \| class` |
| `scope_ref_id` | UUID NULL | NULL for global, org_id for org, cst_id for class |
| `curriculum_id` | UUID FK | |
| `grade_id` | UUID FK | |
| `subject_id` | UUID FK | |
| `book_id` | UUID FK NULL | required for ALL scopes in v1 per **D-69** (column is nullable for forward compat; service layer enforces) |
| `parent_breakdown_id` | UUID FK → `breakdowns.id` NULL | fork lineage |
| `previous_version_id` | UUID FK → `breakdowns.id` NULL | edit lineage (D-18) |
| `status` | TEXT DEFAULT 'draft' | `draft \| published` |
| `total_teaching_days` | INT | |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

INDEX `(scope, scope_ref_id, curriculum_id, grade_id, subject_id, status)` for the "find current published breakdown for X" query.

### `breakdown_chapters`
Per breakdown, the chapters in order with budget.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `breakdown_id` | UUID FK | |
| `book_chapter_id` | UUID FK | |
| `position` | INT | order within breakdown (1, 2, ...) |
| `teaching_days` | INT | total period count for this chapter (D-29) |

UNIQUE `(breakdown_id, position)`.

### `breakdown_slots`
The atomic slots within a breakdown.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `breakdown_id` | UUID FK | |
| `breakdown_chapter_id` | UUID FK | |
| `position` | INT | global sequence position (1..N across whole breakdown) |
| `chapter_position` | INT | position within chapter |
| `slot_type` | TEXT | `lesson \| formative_assessment \| summative_assessment \| revision` (D-59) |
| `lp_type` | TEXT NULL | for lesson slots: one of the valid lp_types per subject |
| `topic_id` | UUID FK → `topics.id` NULL | for lesson and revision slots |
| `anchor_date` | DATE NULL | admin-only (D-7) |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

UNIQUE `(breakdown_id, position)`.

### `breakdown_slot_topics`
For assessment slots that cover multiple topics (D-58). Also used for revision slots.

| Column | Type | Notes |
|---|---|---|
| `breakdown_slot_id` | UUID FK | |
| `topic_id` | UUID FK | |
| `position` | INT | order within the slot's topic set |
| PK `(breakdown_slot_id, topic_id)` | | |

---

## Section 5: Realized slots (per CST)

### `class_lesson_slots`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK | denorm |
| `cst_id` | UUID FK | |
| `breakdown_slot_id` | UUID FK | |
| `position` | INT | copied from breakdown_slot at creation |
| `slot_type` | TEXT | copied |
| `lp_type` | TEXT NULL | copied |
| `topic_id` | UUID FK NULL | copied |
| `anchor_date` | DATE NULL | copied |
| `generated_lp_id` | UUID FK → `generated_lps.id` NULL | resolved on finalize or on demand |
| `status` | TEXT DEFAULT 'planned' | `planned \| taught \| skipped` — materialized column synchronously updated by F2.12 inside the mark-taught transaction (**D-67**, **D-70**). Not a computed view. |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

UNIQUE `(cst_id, position)`.

### `class_assessment_slots`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK | |
| `cst_id` | UUID FK | |
| `breakdown_slot_id` | UUID FK | |
| `position` | INT | |
| `assessment_type` | TEXT | `formative \| summative` |
| `anchor_date` | DATE NULL | |
| `generated_exam_id` | UUID FK → `generated_exams.id` NULL | |
| `status` | TEXT DEFAULT 'scheduled' | `scheduled \| completed \| skipped` |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

UNIQUE `(cst_id, position)`.

### `class_assessment_slot_topics`
The topics covered by this realized assessment (carries the breakdown's `breakdown_slot_topics` forward).

| Column | Type | Notes |
|---|---|---|
| `class_assessment_slot_id` | UUID FK | |
| `topic_id` | UUID FK | |
| `position` | INT | |
| PK `(class_assessment_slot_id, topic_id)` | | |

### `slot_progress`
Event log (D-A5).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `cst_id` | UUID FK | |
| `slot_kind` | TEXT | `lesson \| assessment` |
| `slot_id` | UUID | references either `class_lesson_slots.id` or `class_assessment_slots.id` |
| `action` | TEXT | `taught \| skipped \| completed` |
| `occurred_on` | DATE | when the action happened |
| `recorded_at` | TIMESTAMPTZ DEFAULT NOW() | |
| `notes` | TEXT NULL | |

INDEX `(cst_id, slot_kind, slot_id)` for "has this slot been marked?" queries.

### `cst_sub_slo_coverage`
Materialized view (or table updated by triggers/services) for fast SLO coverage reporting.

| Column | Type | Notes |
|---|---|---|
| `cst_id` | UUID FK | |
| `sub_slo_id` | UUID FK | |
| `status` | TEXT | `taught \| not_taught` |
| `marked_at` | TIMESTAMPTZ | |
| PK `(cst_id, sub_slo_id)` | | |

---

## Section 6: Holidays & Timetable

### `org_holidays`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | UUID FK | |
| `academic_year_id` | UUID FK | |
| `date` | DATE | |
| `name` | TEXT | |

### `school_holiday_overrides`
School can add or remove from Org defaults.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `school_id` | UUID FK | |
| `date` | DATE | |
| `name` | TEXT NULL | only when adding |
| `action` | TEXT | `add \| remove` |

### `cst_holiday_overrides`
Teacher (CST) can add or remove from School defaults.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `cst_id` | UUID FK | |
| `date` | DATE | |
| `name` | TEXT NULL | |
| `action` | TEXT | `add \| remove` |

### `timetables`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `cst_id` | UUID FK | |
| `day_of_week` | INT | 0=Mon..4=Fri (D-27) |
| `start_time` | TIME NULL | |
| `end_time` | TIME NULL | |

UNIQUE `(cst_id, day_of_week)`.

---

## Section 7: Generation (LP / Exam)

### `generated_lps`
Cached at curriculum-topic-lp_type level (D-46, D-56, D-57).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `cache_key` | TEXT UNIQUE NULL | for non-revision: `"{curriculum_id}:{topic_id}:{lp_type}"` |
| `scope` | TEXT | `global \| class` (D-57) |
| `scope_ref_id` | UUID NULL | NULL for global, cst_id for class-scoped |
| `curriculum_id` | UUID FK | |
| `grade_id` | UUID FK | |
| `subject_id` | UUID FK | |
| `topic_id` | UUID FK NULL | NULL for revision LPs |
| `revision_topic_set_hash` | TEXT NULL | for revision LPs: SHA-256 of sorted topic_ids |
| `lp_type` | TEXT | |
| `status` | TEXT | `PENDING \| IN_FLIGHT \| READY \| ERROR` |
| `job_id` | TEXT NULL | LP Assistant v3 job id |
| `content` | TEXT NULL | HTML |
| `content_bilingual` | TEXT NULL | |
| `covered_sub_slo_ids` | UUID[] NULL | from Schema's lp_tagging post-process (D-22) |
| `requested_sub_slo_ids` | UUID[] NULL | intent at dispatch — the sub-SLOs we asked LP Assistant to cover via `custom_prompt`. Set on the initial PENDING insert; never changed afterwards. See [features/lp-slo-injection-and-linkage](../../features/lp-slo-injection-and-linkage/README.md). |
| `tagging_status` | TEXT DEFAULT 'pending' | `pending \| done \| failed` |
| `cost_usd` | NUMERIC NULL | (D-10) |
| `tokens_input` | INT NULL | |
| `tokens_output` | INT NULL | |
| `model` | TEXT NULL | |
| `error_message` | TEXT NULL | |
| `lp_assistant_response_raw` | JSONB NULL | full response for debugging |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

INDEX on `cache_key` (for lookup before generating).  
INDEX on `(status)` for batch-progress dashboard.  
INDEX on `(scope, scope_ref_id)` for "what LPs does this CST own?"

### `generated_exams`
Same shape, cached at `(curriculum, [topic_ids], generation_type, question_config_hash)`.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `cache_key` | TEXT UNIQUE NULL | `"{curriculum_id}:{topic_ids_hash}:{gen_type}:{config_hash}"` |
| `scope` | TEXT | `global \| class` |
| `scope_ref_id` | UUID NULL | |
| `curriculum_id` | UUID FK | |
| `grade_id` | UUID FK | |
| `subject_id` | UUID FK | |
| `topic_ids_hash` | TEXT | SHA-256 of sorted topic_ids |
| `generation_type` | TEXT | `exam \| class_assessment` |
| `question_config_hash` | TEXT | hash of the full UG_EG request config |
| `status` | TEXT | same lifecycle |
| `job_id` | TEXT NULL | UG_EG v2 job id |
| `result` | JSONB NULL | the exam_json from UG_EG |
| `exam_paper_html` | TEXT NULL | the HTML rendering |
| `question_sub_slo_tags` | JSONB NULL | per-question sub-SLO tagging (post-process) |
| `tagging_status` | TEXT DEFAULT 'pending' | |
| `cost_usd` | NUMERIC NULL | |
| `tokens_input`, `tokens_output` | INT NULL | |
| `model` | TEXT NULL | |
| `error_message` | TEXT NULL | |
| `ug_eg_response_raw` | JSONB NULL | |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

### `exam_results`
Mastery data entered by teacher post-exam (D-31, D-32).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `class_assessment_slot_id` | UUID FK | |
| `students_present` | INT | denominator |
| `recorded_by_teacher_id` | UUID FK NULL | |
| `recorded_at` | TIMESTAMPTZ | |

### `exam_question_results`
Per-question class-level scores.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `exam_result_id` | UUID FK | |
| `question_index` | INT | index into the exam_json |
| `sub_slo_id` | UUID FK NULL | from question tagging |
| `students_correct` | INT | numerator |
| `marks_total` | INT | |
| `marks_earned_avg` | NUMERIC NULL | optional |

### `sub_slo_mastery`
Rolled up per CST per sub-SLO per assessment.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `cst_id` | UUID FK | |
| `sub_slo_id` | UUID FK | |
| `class_assessment_slot_id` | UUID FK | |
| `mastery_percent` | NUMERIC | 0..100 |
| `assessed_on` | DATE | |
| `created_at` | TIMESTAMPTZ | |

INDEX `(cst_id, sub_slo_id, assessed_on)` for trend queries.

---

## Section 8: Webhooks & jobs

### `webhook_events`
Audit log of incoming webhook payloads.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `source` | TEXT | `lp_assistant \| ug_eg` |
| `job_id` | TEXT | |
| `payload` | JSONB | |
| `processed` | BOOL DEFAULT FALSE | |
| `received_at` | TIMESTAMPTZ DEFAULT NOW() | |

---

## Section 9: Relationships diagram (ASCII)

```
organizations ─┬─ org_admins (1:N)
               ├─ schools (1:N)
               │       ├─ academic_years (1:N)
               │       │       └─ school_classes (1:N)
               │       │              └─ class_subject_teachers (1:N)   ← THE TEACHING UNIT
               │       │                     ├─ cst_state (1:1)
               │       │                     ├─ timetables (1:N)
               │       │                     ├─ cst_holiday_overrides (1:N)
               │       │                     ├─ class_lesson_slots (1:N)
               │       │                     │       └─ slot_progress
               │       │                     └─ class_assessment_slots (1:N)
               │       │                             ├─ class_assessment_slot_topics
               │       │                             ├─ slot_progress
               │       │                             └─ exam_results
               │       │                                     └─ exam_question_results
               │       │                                             ↳ sub_slo_mastery
               │       ├─ org_holidays
               │       └─ school_holiday_overrides
               └─ teachers (1:N)
                       └─ assigned to class_subject_teachers

curriculums ──┬─ slos ── sub_slos
              ├─ books ── book_chapters ── topics
              │           └─ book_chapter_slos    (chapter ↔ SLO)
              │                              ↳ topic_sub_slos (topic ↔ SubSLO)
              └─ breakdowns
                     ├─ breakdown_chapters
                     └─ breakdown_slots
                            └─ breakdown_slot_topics
                            
generated_lps (cached, global or class scope)
       ↳ referenced by class_lesson_slots.generated_lp_id

generated_exams (cached, global or class scope)
       ↳ referenced by class_assessment_slots.generated_exam_id

webhook_events (audit)
```

---

## Section 10: Migration SQL (cutover)

The v2 cutover **drops the staging DB and recreates from scratch** (D-34). One migration file: `server/src/dars/migrations/20260516000000_v2_cutover.sql`.

Structure:
1. `DROP TABLE` (cascade) for every existing table — clean slate
2. `CREATE TABLE` for the schema above in dependency order
3. Seed data INSERTs (subjects, grades, curriculums, etc. — fixed lookup data)

The seed for Dars Curriculum + English G1 + 1 org/school/class is a **separate seed script** at `server/src/dars/seeds/v2_seed.py` (Python, not SQL, so we can author rich content with multi-line strings and dict structures).

Migration order within the CREATE TABLE block:

1. `grades`, `subjects`, `curriculums` (lookup, no FKs)
2. `slos`, `sub_slos`
3. `books`, `book_chapters`, `topics`
4. `book_chapter_slos`, `topic_sub_slos`
5. `organizations`, `org_admins`
6. `schools`, `teachers`
7. `academic_years`, `school_classes`
8. `class_subject_teachers`, `cst_state`
9. `timetables`
10. `org_holidays`, `school_holiday_overrides`, `cst_holiday_overrides`
11. `breakdowns`, `breakdown_chapters`, `breakdown_slots`, `breakdown_slot_topics`
12. `class_lesson_slots`, `class_assessment_slots`, `class_assessment_slot_topics`
13. `slot_progress`, `cst_sub_slo_coverage`
14. `generated_lps`, `generated_exams`
15. `exam_results`, `exam_question_results`, `sub_slo_mastery`
16. `webhook_events`

Exact SQL is generated per-phase as needed; this document fixes shape and order.

---

## Section 11: Indexes summary

Critical indexes beyond the natural PKs:

- `organizations`: `(api_key_hash)` for auth lookup
- `class_subject_teachers`: `(school_class_id, subject_id)` UNIQUE; `(teacher_id)`; `(org_id)`
- `slos`: `(curriculum_id, grade_id, subject_id)`; `(curriculum_id, grade_id, subject_id, code)` UNIQUE
- `sub_slos`: `(slo_id)`; `(slo_id, code)` UNIQUE
- `topics`: `(book_chapter_id, topic_number)` UNIQUE
- `breakdowns`: `(scope, scope_ref_id, curriculum_id, grade_id, subject_id, status)` for current-breakdown lookups
- `breakdown_slots`: `(breakdown_id, position)` UNIQUE
- `class_lesson_slots`: `(cst_id, position)` UNIQUE; `(cst_id, status)`
- `class_assessment_slots`: `(cst_id, position)` UNIQUE
- `slot_progress`: `(cst_id, slot_kind, slot_id)`; `(cst_id, occurred_on)` for activity queries
- `generated_lps`: `cache_key` UNIQUE WHERE `scope='global'`; `(status)` for batch dashboard
- `generated_exams`: same pattern
- `sub_slo_mastery`: `(cst_id, sub_slo_id, assessed_on)`
- `webhook_events`: `(source, job_id)`
