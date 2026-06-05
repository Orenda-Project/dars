# Data model — Core Book Import

**One schema delta:** a new `import_runs` table. The import itself only **reads** core
and **upserts** existing Dars curriculum tables (no shape changes to those).

## New table — `import_runs`

Migration `server/src/dars/migrations/<ts>_import_runs.sql`. Tracks one background
import execution (D-1).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `core_book_id` | INT NOT NULL | the `fde_staging.book_library_book.id` imported |
| `curriculum_id` | UUID NOT NULL | resolved Dars curriculum (the cell) |
| `grade_id` | UUID NOT NULL | resolved Dars grade |
| `subject_id` | UUID NOT NULL | resolved Dars subject |
| `dars_book_id` | UUID NULL | the deterministic Dars `books.id`; set once the book upserts |
| `status` | TEXT NOT NULL | `pending` \| `running` \| `succeeded` \| `failed` |
| `current_step` | TEXT NULL | one of the Step names, or null |
| `steps` | JSONB NOT NULL DEFAULT '{}' | per-step state: `{slos:{status,count}, sub_slos:{…}, book_chapters:{…}, topics:{…}, mappings:{…}}` |
| `counts` | JSONB NOT NULL DEFAULT '{}' | final row counts: `{slos, sub_slos, chapters, topics, topic_sub_slos, book_chapter_slos}` |
| `warnings` | JSONB NOT NULL DEFAULT '[]' | non-fatal notes (e.g. chapters with no page range) |
| `error` | TEXT NULL | failure message (set when `status='failed'`) |
| `started_by` | TEXT NULL | admin identifier from `require_admin` (email/username) |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | bumped on each step transition |

Index: `CREATE INDEX ix_import_runs_status ON import_runs(status);`
(used by the one-running-at-a-time guard, D-8) and
`CREATE INDEX ix_import_runs_created_at ON import_runs(created_at DESC);` (list ordering).

Use `gen_random_uuid()` (pgcrypto, already available) — `import_runs.id` is server-side,
not a deterministic seed UUID.

## Core (read-only) — `fde_staging`

Read exactly as the script does (see [03-reference-etl-script.md](03-reference-etl-script.md)):

| Table | Used for |
|---|---|
| `book_library_book` | book metadata + `book_text`; joined to grade/subject via `slo_gradesubject` → `slo_grade` / `slo_subject` |
| `book_library_bookchapter` | chapter index (chapter_number, title, start_page, end_page, status); `deleted_at IS NULL` |
| `slo_ncpslo` | top-level SLOs; joined to grade/subject; `is_active = TRUE` |
| `slo_gradesubject`, `slo_grade`, `slo_subject` | resolve the cell + filter by `short_code` |

Connection: read-only, `SET search_path TO fde_staging, public` (D-5).

## Dars (read-write) — existing tables, upserts only

`curriculums`, `slos`, `sub_slos`, `books`, `book_chapters`, `topics`,
`topic_sub_slos`, `book_chapter_slos` — all written with `ON CONFLICT … DO UPDATE`
keyed on the deterministic UUIDs / natural unique keys (D-6). No column changes to any
of these; the `core-book-import` feature reuses the schema the book-viewer + seed
already rely on. `sub_slos.recommended_lp_type` already exists (added by the
ncp-english-g1-seed migration).

## Idempotency keys (D-6)

Deterministic UUID v5 from `SEED_NAMESPACE` (= the script's namespace), keys generalised
from the resolved cell codes `<CURR>/<GRADE>/<SUBJ>`:

```
curriculum:<CURR>
slo:<CURR>:<GRADE>:<SUBJ>:<code>
sub_slo:<CURR>:<GRADE>:<SUBJ>:<code>
book:<CURR>:<GRADE>:<SUBJ>:<core_book_id>
book_chapter:<CURR>:<GRADE>:<SUBJ>:<core_book_id>:<chapter_number>
topic:<CURR>:<GRADE>:<SUBJ>:ch<chapter_number>:1
```
