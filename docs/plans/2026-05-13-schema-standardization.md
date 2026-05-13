---
type: plan
status: draft
created: 2026-05-13
branch: feat/lookup-table-standardization
---

# Lookup Table Standardization

## Problem

Three data bank lookup tables (`grades`, `subjects`, `curriculums`) use natural keys as their PKs instead of UUIDs. This causes:
- Inconsistency — every other table uses uuid PKs
- No `created_at` / `updated_at` — can't track when reference data was added or changed
- Staging → production data migration will be fragile (natural key collisions)

`slos` is also missing `updated_at` and the `gen_random_uuid()` default on its `id`.

## Goal

Every data bank table has: `id uuid PK`, `created_at`, `updated_at`.

## Approach

Keep `code` as a `UNIQUE` constraint (not PK) so all existing FK references (`books.curriculum`, `slos.curriculum`, `slos.subject`, `slos.grade`, `clients.curriculum`, etc.) continue to work without touching referencing tables.

## Tables affected

| Table | Change |
|---|---|
| `grades` | Add `id uuid PK`, demote `code` to UNIQUE, add `created_at` + `updated_at` |
| `subjects` | Add `id uuid PK`, demote `code` to UNIQUE, add `created_at` + `updated_at` |
| `curriculums` | Add `id uuid PK`, demote `code` to UNIQUE, add `created_at` + `updated_at` |
| `slos` | Add `updated_at`, add `DEFAULT gen_random_uuid()` to `id` |

## Tables NOT touched

`books`, `book_chapters`, `topics`, `topic_slos` — already standardized.

## Files to change

| File | Change |
|---|---|
| `server/src/dars/migrations/20260513000008_lookup_table_standardization.sql` | New migration |
| `server/src/dars/lookup/models.py` | Grade, Subject — add uuid PK, timestamps (already done by user) |
| `server/src/dars/curriculum_data/models.py` | CurriculumData — add uuid PK, timestamps (already done by user) |
| `server/src/dars/curriculum/models.py` | Slo — add updated_at, fix id default |

## Migration steps (SQL)

```sql
-- grades
ALTER TABLE grades ADD COLUMN id uuid NOT NULL DEFAULT gen_random_uuid();
ALTER TABLE grades DROP CONSTRAINT grades_pkey;
ALTER TABLE grades ADD PRIMARY KEY (id);
ALTER TABLE grades ADD CONSTRAINT grades_code_key UNIQUE (code);
ALTER TABLE grades ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE grades ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- subjects
ALTER TABLE subjects ADD COLUMN id uuid NOT NULL DEFAULT gen_random_uuid();
ALTER TABLE subjects DROP CONSTRAINT subjects_pkey;
ALTER TABLE subjects ADD PRIMARY KEY (id);
ALTER TABLE subjects ADD CONSTRAINT subjects_code_key UNIQUE (code);
ALTER TABLE subjects ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE subjects ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- curriculums
ALTER TABLE curriculums ADD COLUMN id uuid NOT NULL DEFAULT gen_random_uuid();
ALTER TABLE curriculums DROP CONSTRAINT curriculums_pkey;
ALTER TABLE curriculums ADD PRIMARY KEY (id);
ALTER TABLE curriculums ADD CONSTRAINT curriculums_code_key UNIQUE (code);
ALTER TABLE curriculums ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE curriculums ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- slos
ALTER TABLE slos ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE slos ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
```

## FK safety

No FK references to `grades`, `subjects`, or `curriculums` need to change — they all reference the `code` column which remains unique. The DB will enforce this via the new UNIQUE constraint instead of the old PK constraint.

## Verification

- `make db-migrate` applies cleanly
- `uv run pytest` passes
- `\d grades` shows `id uuid PK`, `code int UNIQUE`, `created_at`, `updated_at`
</content>
</invoke>