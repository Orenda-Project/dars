# Phase 1 — Backend

Bead `feat-core-book-import-phase-1`. Branch from `staging`. PRs → `staging`. Features
numbered F-1.N, in order. References: decision log (D-1…D-8), data model, reference ETL.

---

## F-1.1 — Migration: `import_runs`

**Spec.** New migration `server/src/dars/migrations/<ts>_import_runs.sql` creating the
`import_runs` table + the two indexes per [02-data-model.md](02-data-model.md). Plain SQL,
append-only, runs on Railway deploy (never run manually).

**Acceptance.** Migration file present; columns/indexes match the data model; uses
`gen_random_uuid()`; no edits to other migrations.

**Dependencies.** None.

---

## F-1.2 — Vendor the breakdown prompt + port the lp_type classifier (D-4)

**Spec.** Copy the Schema English breakdown prompt text into the Dars package at
`server/src/dars/v2_api/prompts/slo_breakdown_english.txt` (read via `importlib.resources`
or a package path — never an absolute workstation path). Port
`scripts/lp_type_classifier.py` into the service module (Claude Haiku, temp 0, 5-value
enum, cached system block, retry-once-then-raise). No behaviour change vs the script.

**Acceptance.** Prompt loads from the package on a clean checkout (no `/home/...` path).
A unit test classifies a known sub-SLO statement to the expected enum value (mock the
Anthropic client — no live call in CI).

**Dependencies.** None (parallel with F-1.1).

---

## F-1.3 — Core-book browse endpoint

**Spec.** `GET /api/v2/admin/core-books` (admin-gated, D-5). Queries
`fde_staging.book_library_book` joined to grade/subject, filtered `status='OnProd' AND
is_active AND deleted_at IS NULL`, optional `?search=` on title. Returns
`[{core_book_id, title, publisher, edition, published_year, total_chapters, grade,
subject, status, already_imported}]`. `already_imported` = the deterministic
`book:<curr>:<grade>:<subj>:<core_id>` UUID exists in Dars `books` (curriculum = active
Dars curriculum, or all candidate curriculums). If `effective_core_db_url` is empty →
`503` (D-7). Structured logging (rule 11).

**Acceptance.** With core configured, returns the OnProd book list incl. book 1171 with
`grade='G1'`, `subject='Eng'`. `?search=english` filters. Without core config → 503 with a
clear message. Non-admin → 401/403.

**Dependencies.** None.

---

## F-1.4 — Import service (ported ETL)

**Spec.** New `server/src/dars/v2_api/book_import_service.py` porting the 5 steps from
[03-reference-etl-script.md](03-reference-etl-script.md), generalised to the resolved cell
(D-2, D-6): resolve grade_id/subject_id from the core book's short codes (422 if no Dars
lookup); curriculum from the request (default active); deterministic UUIDs from the cell
codes; **no G1/Eng assert**. Opens its own core (read-only, search_path) + Dars (rw, single
transaction) connections (D-5). Reports progress by updating the passed `import_runs` row
per step (`current_step`, `steps`, `counts`, `warnings`). On error: roll back the Dars tx,
set `status='failed'` + `error` (the run-row update is outside the rolled-back tx).

**Acceptance.** Unit-tested with mocked core rows + mocked Anthropic: produces the expected
upsert calls per step, populates `counts`, records a warning for a null-page-range chapter,
and marks `failed` + rolls back on an injected mid-step error. No live DB/LLM in CI.

**Dependencies.** F-1.2.

---

## F-1.5 — Import endpoints + background job (D-1, D-8)

**Spec.** Admin-gated:
- `POST /api/v2/admin/book-imports` body `{core_book_id, curriculum_id?}` → resolve the
  cell, **409** if any `import_runs.status='running'` (D-8), **503** if core unconfigured,
  else insert an `import_runs` row (`pending`), schedule a FastAPI background task that runs
  F-1.4 (flipping the row to `running` then `succeeded`/`failed`), and return
  `202 {import_run_id}`.
- `GET /api/v2/admin/book-imports/{id}` → the run row (status, current_step, steps, counts,
  warnings, error, dars_book_id).
- `GET /api/v2/admin/book-imports` → recent runs (ordered by created_at desc) for a history
  list.

Register the router in `main.py`. Structured logging on entry/exit/error (rule 11).

**Acceptance.** POST returns 202 + id; a second POST while one is running → 409; GET reflects
progress transitions; GET list returns recent runs. Background task failure surfaces as
`status='failed'` with `error` (not a 500 on the POST). Endpoints 503 when core unconfigured.

**Dependencies.** F-1.1, F-1.3, F-1.4.

## Notes from execution
*(append-only)*
