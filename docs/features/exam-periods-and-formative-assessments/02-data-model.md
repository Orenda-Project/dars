# Data Model

Ground truth for the schema. Migration SQL cites this doc; this doc cites the SQL. Every table/column/FK/index/migration-order change for this feature lives here.

All new tables follow the project rule: **filter by tenant**. Exam-period / breakdown-holiday rows are reached only through their parent `syllabus_breakdowns` row, which is itself scoped; reads always join through the breakdown.

---

## New table: `exam_periods` (Phase 1, D-1)

Reserved non-teaching date ranges on a Syllabus Breakdown for exams.

```sql
CREATE TABLE exam_periods (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    syllabus_breakdown_id UUID NOT NULL REFERENCES syllabus_breakdowns(id) ON DELETE CASCADE,
    start_date            DATE NOT NULL,
    end_date              DATE NOT NULL,
    name                  TEXT NOT NULL,           -- e.g. 'Mid-term exams'
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_exam_periods_breakdown ON exam_periods(syllabus_breakdown_id);
```

- `ON DELETE CASCADE`: deleting a breakdown removes its exam periods.
- Multiple rows per breakdown (the user's "1–20 Aug, then so on").
- `end_date >= start_date` enforced in the service layer (advisory per D-4), not a CHECK, to keep validation uniform with chapter ranges.

## New table: `breakdown_holidays` (Phase 1, D-14)

Reserved non-teaching date ranges on a Syllabus Breakdown for **general holidays** (Eid, public holidays, breaks) that should inherit down to every class plan on that (curriculum, grade, subject) triple. Same shape as `exam_periods`; kept as a separate table so "exam" and "holiday" stay semantically distinct (D-1 rationale) and the admin UI can present two clearly-labelled sections.

```sql
CREATE TABLE breakdown_holidays (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    syllabus_breakdown_id UUID NOT NULL REFERENCES syllabus_breakdowns(id) ON DELETE CASCADE,
    start_date            DATE NOT NULL,
    end_date              DATE NOT NULL,
    name                  TEXT NOT NULL,           -- e.g. 'Eid-ul-Fitr'
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_breakdown_holidays_breakdown ON breakdown_holidays(syllabus_breakdown_id);
```

- Both `exam_periods` and `breakdown_holidays` are *date ranges* (admins think in spans: "Eid week", "1–20 Aug exams"). Single-day holidays are a 1-day range (`start_date == end_date`).
- These are **distinct from** `org_holidays` (prior D-26). Org holidays remain org-scoped and continue to inherit org→school→CST. Breakdown holidays inherit through the (curriculum, grade, subject) triple. Both feed the same final teaching-day exclusion set. See D-14, D-15.

## Migration

One new SQL file in `server/src/dars/migrations/`, named with a timestamp after the latest existing migration:

```
20260610000000_exam_periods_and_breakdown_holidays.sql
```

Creates both tables + indexes. Append-only; never edited after merge. Runs automatically on Railway deploy (project rule 7).

---

## Changed: planner contract `PlanUnit` (Phase 2, D-6/D-7/D-13)

`server/src/dars/breakdown/planner_models.py`

| Field | Before | After |
|-------|--------|-------|
| `slot_type` | *(absent)* | `str = Field(default='lesson')` — `∈ ('lesson','formative_assessment')` (D-6, D-12, D-13) |
| `lp_type` | required `str` | `str \| None` — required iff `slot_type='lesson'` (D-7) |
| `topic_ids`, `slo_ids`, `topic_text`, `sequence`, `rationale` | unchanged | unchanged |

`validate_plan` (`breakdown/planner.py`) changes per D-7/D-8:
- exactly `period_count` units total (lessons + FAs)
- `lp_type ∈ VALID_LP_TYPES[subject]` **only** when `slot_type='lesson'`; absent when FA
- every chapter SLO covered ≥1× across lesson **and** FA units
- `sequence` a permutation of 1..period_count (unchanged)

No DB column for the planner contract — it's an in-memory I/O shape. The *persisted* result of an FA unit is a `class_assessment_slots` row (existing table, D-9), not a new column.

---

## Used (not changed): existing assessment tables (Phase 2/3)

These already exist (v2 cutover, lines 366–399). This feature **populates** them; no schema change.

- `class_assessment_slots` — `assessment_type='formative'`, `book_chapter_id`, `status='scheduled'`, `generated_exam_id` (set in Phase 3), shared `position` with lesson slots.
- `class_assessment_slot_topics` — `(class_assessment_slot_id, topic_id, position)` covered-topic grouping.
- `generated_exams` — the exam cache/output table the Phase 3 entry point writes to (existing `generated_exams` service).

---

## Calendar exclusion data flow (Phase 1, D-2/D-3/D-15)

No schema change — a derivation change. The set passed as `holidays` to `compute_teaching_days` is augmented:

```
teaching_days = compute_teaching_days(
    start, end, weekday_set,
    holidays = effective_holidays            # existing: org ± school ± CST (prior D-26)
             ∪ breakdown_exam_dates          # NEW: expanded from exam_periods (D-2)
             ∪ breakdown_holiday_dates        # NEW: expanded from breakdown_holidays (D-14)
)
```

- **Admin display** (`derived_teaching_days` in `chapter_calendar.py` via `router_syllabus`): holidays = the breakdown's own exam + holiday dates (no org/school/CST context exists for a global breakdown — prior `resolve_breakdown_holidays` returns empty).
- **Teacher projection** (`chapter_slot_count`, `project_cst_schedule`): holidays = `get_effective_holidays(cst_id)` ∪ the resolved breakdown's exam + holiday dates (D-3).
- Expansion helper: `expand_ranges(rows) -> set[date]` walks each `[start_date, end_date]` inclusive. Lives next to the calendar helpers.
