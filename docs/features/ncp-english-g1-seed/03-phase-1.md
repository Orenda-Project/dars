# Phase 1 — Direct ETL into Dars staging (sole phase per D-18)

**Goal:** one PR ships everything: the additive migration, the heuristic updates, the import script, the script run against Dars staging, and the deletion of stale `scripts/import_books.py`. After merge + deploy + script-run, Dars staging has the NCP curriculum with English G1 SLOs, sub-SLOs, book 1171, chapters, topics, and topic↔sub-SLO mappings — alongside the existing Dars synthetic seed, which is untouched.

**Bead:** `feat-ncp-english-g1-seed-phase-1-extract` (opened 2026-05-20; will be re-titled to "direct ETL" in the close-out commit message).

**Branch:** `feat/ncp-english-g1-seed-phase-1` from `staging`.

---

## Features

### F1.1 — Migration: add `recommended_lp_type` to `sub_slos`

**Spec (per `D-12`):**
- New file `server/src/dars/migrations/<YYYYMMDDHHMMSS>_sub_slos_add_recommended_lp_type.sql`
- `ALTER TABLE sub_slos ADD COLUMN recommended_lp_type TEXT;` (nullable, no default, no backfill)
- Updates `docs/plans/2026-05-15-dars-v2-rebuild/02-data-model.md` §sub_slos in the same PR (add the column row + a note on precedence)

**Acceptance:**
- Migration file present, named per the existing convention (YYYYMMDDHHMMSS_<slug>.sql)
- Column visible after deploy: `\d sub_slos` on Dars staging shows `recommended_lp_type | text |  |  |`
- Existing Dars sub-SLO rows all NULL after migration
- v2 rebuild's `02-data-model.md` updated

**Dependencies:** none.

---

### F1.2 — Update `lp_type_heuristics` and `auto_build_service` for sub-SLO precedence

**Spec (per `D-13`):**
- Edit `server/src/dars/breakdown/lp_type_heuristics.py`:
  - Add optional `sub_slo_recommended_lp_type: str | None = None` parameter
  - Precedence: sub-SLO's value > parent SLO's `recommended_lp_type` > subject default chain
  - Docstring updated
- Edit `server/src/dars/breakdown/auto_build_service.py`:
  - Topic-lp_type query joins `sub_slos`, picks its `recommended_lp_type` first; falls back to `slos.recommended_lp_type`
  - Behavior for existing Dars data unchanged (sub-SLO column NULL → falls back)
- Add pure-Python tests: sub-SLO set / parent set / both set / neither set

**Acceptance:**
- New tests pass
- All existing tests pass (no regression on Dars path)
- `git grep recommended_lp_type` shows the heuristic + service both reference the sub-SLO column

**Dependencies:** F1.1 (migration must land first so the column exists when code is deployed).

---

### F1.3 — Script scaffold + dual DB connections

**Spec:**
- New file `dars/scripts/import_ncp_english_g1.py`
- CLI: `--book-id` (default `1171`), `--dry-run` (read + plan, no writes), `--verbose`
- Reads env vars: `CORE_STAGING_DB_HOST/PORT/NAME/USER/PASSWORD`, `DARS_STAGING_DATABASE_URL`, `ANTHROPIC_API_KEY`
- Opens fde_staging connection: read-only via `BEGIN READ ONLY;`, `search_path = fde_staging, public`
- Opens Dars staging connection: read-write, single transaction wrapping all upserts
- On any error: rolls back the Dars transaction, closes both connections, exits non-zero
- On success (and not dry-run): commits the Dars transaction
- All queries against fde_staging use `fde_staging.` schema prefix to avoid the search_path footgun seen during planning
- Logging: entry/exit at INFO with row counts per step, errors at ERROR with exc_info

**Acceptance:**
- `--dry-run` exits 0 against current Dars staging with output showing what would be upserted (no writes)
- Missing creds → fast clear error mentioning which env var
- Deliberately-failing INSERT against fde_staging is rejected (sanity check the READ ONLY guard, can be a one-time manual confirmation)

**Dependencies:** F1.1, F1.2 (the script targets the post-migration schema).

---

### F1.4 — Claude lp_type classifier helper

**Spec (per `D-11`, `D-14`):**
- New file `dars/scripts/lp_type_classifier.py`
- Uses `anthropic` SDK (already in deps)
- Function `classify_lp_type(parent_slo_statement: str, sub_slo_statement: str) -> str`
  - Returns one of `{reading, comprehension_word_meanings, comprehension_qa, grammar, creative_writing}`
  - Model: `claude-haiku-4-5-20251001`
  - `temperature=0`
  - System block (cached): enum definitions + 1 example per value
  - User block (per-request): the two statements
  - Validates output in enum; one retry with stricter prompt; second miss raises
- Batch helper `classify_all(records: list[dict]) -> list[dict]` for cache reuse

**Acceptance:**
- Unit test (mocked client) exercises validation + retry path
- `--smoke` flag in classifier (developer-only) classifies 5 known sub-SLOs; output logged

**Dependencies:** none (but used by F1.6).

---

### F1.5 — Upsert NCP curriculum + SLOs

**Spec:**
- In the script: `import_ncp_curriculum_row()`:
  - `INSERT INTO curriculums (id, code, label) VALUES (<deterministic UUID via uuid5("curriculum:NCP")>, 'NCP', 'National Curriculum of Pakistan') ON CONFLICT (code) DO NOTHING`
  - Returns the curriculum row's UUID
- Function `import_ncp_slos(curriculum_id, grade_id, subject_id)`:
  - SQL against fde_staging: `slo_ncpslo ⋈ slo_gradesubject ⋈ slo_grade ⋈ slo_subject` filtered English × G1, `is_active=TRUE`
  - Selects: `ncp_slo_id`, `slo_statement`, `category` (drops `domain`, `language_skills` per D-11)
  - For each row, upsert into Dars `slos`: `INSERT ... ON CONFLICT (curriculum_id, grade_id, subject_id, code) DO UPDATE SET statement = EXCLUDED.statement, updated_at = NOW()`
  - SLO `position` derived from row order (1, 2, …) sorted by `ncp_slo_id`
  - `domain` column in Dars `slos` stays NULL for NCP rows (existing schema allows it)
  - Returns dict `{ncp_slo_id: dars_slo_uuid}` for downstream steps

**Acceptance:**
- Dry-run output lists N SLOs to insert with codes
- After real run, `SELECT COUNT(*) FROM slos WHERE curriculum_id = <NCP>` = N (logged in script output)
- Re-run is a no-op (zero new inserts; logged)
- `SELECT COUNT(*) FROM curriculums` shows 4 (3 existing + NCP)

**Dependencies:** F1.3.

---

### F1.6 — Sub-SLO breakdown + classify + upsert

**Spec (per `D-5`, `D-11`):**
- Function `import_sub_slos(slo_code_to_uuid: dict[str, UUID])`:
  - Imports (or subprocesses) `Schema.services.slo_mapping.get_sub_ncp_slos_for_mapping`
  - Calls with `grade_label="Grade One"`, `subject_key="english"`, `force_refresh=False`
  - Saves the breakdown markdown to a log file in `/tmp/` (audit, not committed)
  - Parses rows → `{code, statement, parent_slo_code}`
  - For each, looks up `parent_slo_statement` from the slos in F1.5 (need it as context for the classifier)
  - Calls `lp_type_classifier.classify_lp_type(parent_slo_statement, sub_slo_statement)` for `lp_type`
  - Upserts into Dars `sub_slos`: `INSERT ... ON CONFLICT (slo_id, code) DO UPDATE SET statement = EXCLUDED.statement, recommended_lp_type = EXCLUDED.recommended_lp_type, position = EXCLUDED.position, source = 'schema_breakdown', updated_at = NOW()`
  - `position` derived from row order within parent SLO

**Acceptance:**
- Every NCP sub-SLO row has non-null `recommended_lp_type`
- All five enum values appear at least once across the result (sanity check; if one is never assigned, log a WARN — possible but suspicious)
- Re-run is a no-op (dependent on classifier determinism + same Schema output)
- Total Claude API cost logged in script output and PR description

**Dependencies:** F1.4, F1.5.

---

### F1.7 — Upsert book 1171 + chapters

**Spec (per `D-15`, `D-16`):**
- Function `import_book_and_chapters(book_id: int, curriculum_id, grade_id, subject_id)`:
  - Reads `fde_staging.book_library_book` row for `book_id`
  - Asserts: `status='OnProd'`, `is_active=TRUE`, joined grade='G1', subject='Eng'. If mismatched, raise with a clear message (prevents accidentally seeding the wrong book)
  - Reads `fde_staging.book_library_bookchapter` rows for `book_id`, no `is_active` filter, ordered by `chapter_number`
  - Upserts book into Dars `books`: `INSERT (curriculum_id, grade_id, subject_id, title, publisher, edition, published_year, total_chapters, pdf_url, book_text) VALUES (...) ON CONFLICT (curriculum_id, grade_id, subject_id, title) DO UPDATE SET book_text = EXCLUDED.book_text, total_chapters = EXCLUDED.total_chapters, ..., updated_at = NOW()`
  - Note: the v2 `books` schema's natural unique should be the chosen ON CONFLICT key; if it's something else, adapt to the schema (D-21 if a new natural key is needed)
  - For each chapter row: slice `book.book_text` to elements where `pdf_page_no BETWEEN start_page AND end_page`; concatenate `text` fields (or store the raw sub-array — choose during execution, log the choice)
  - Upserts each chapter into Dars `book_chapters`: `INSERT (book_id, chapter_number, title, start_page, end_page, chapter_text, status) VALUES (...) ON CONFLICT (book_id, chapter_number) DO UPDATE SET title = EXCLUDED.title, ..., updated_at = NOW()`
  - `status` is `'published'` for OnProd source rows, `'draft'` for the 4 stub rows. Documents this in script logs.

**Acceptance:**
- After run: 1 NCP book row, 12 NCP chapter rows in Dars staging
- All 12 chapters have non-empty `chapter_text` (since the JSON-slice covers all 12 page ranges — verified during planning investigation)
- Re-run is a no-op

**Dependencies:** F1.5.

---

### F1.8 — Topic extraction + topic↔sub-SLO mapping

**Spec (per `D-6`, `D-7`):**
- Function `import_topics_and_mappings(chapters: list[dict], sub_slo_code_to_uuid: dict[str, UUID])`:
  - For each chapter, try Schema's topic extraction first. If Schema gives back topics + sub-SLO mapping per topic, use it. Otherwise fallback per D-7: one synthetic topic per chapter, flagged in logs as synthetic
  - Upserts into `topics`: `INSERT (book_chapter_id, topic_number, title, text) VALUES (...) ON CONFLICT (book_chapter_id, topic_number) DO UPDATE SET title = EXCLUDED.title, text = EXCLUDED.text, updated_at = NOW()`
  - For each topic-to-sub-SLO mapping, calls Schema's `map_topics_to_ncp_slos`
  - Upserts into `topic_sub_slos`: `INSERT (topic_id, sub_slo_id) VALUES (...) ON CONFLICT (topic_id, sub_slo_id) DO NOTHING`
  - Derived: `book_chapter_slos` — populated from the union of parent SLOs of the topics in each chapter; `INSERT (book_chapter_id, slo_id) ... ON CONFLICT DO NOTHING`

**Acceptance:**
- Every chapter has ≥1 topic (synthetic or real)
- Every topic with `is_synthetic_fallback` is logged (count in PR description)
- Every `topic_sub_slos` row references a sub-SLO that exists in `sub_slos` (FK integrity)
- Re-run is a no-op

**Dependencies:** F1.6, F1.7.

---

### F1.9 — Run on staging, verify, delete `import_books.py`, open PR

**Spec:**
- After F1.1's migration is applied on Railway staging (this requires the migration commit to be on the feature branch; the deploy applies it when the PR merges. So this step actually runs AFTER PR merge — see acceptance below):

  Step order: commit all code → push → open PR → user reviews → user merges → Railway deploys F1.1's migration → user runs the script locally pointing at Dars staging.

- The script run logs all counts; outputs go into a comment on the PR (or this phase doc's `## Notes from execution` appendix)
- After script run, smoke-check via `/api/v2/curriculums/NCP/grades/1/subjects/Eng/slos` (or equivalent existing endpoint) returns the new data
- `git rm scripts/import_books.py` (D-20) — done before opening the PR
- PR title: `feat(seed): NCP English G1 — direct ETL into Dars staging`
- PR body: row counts per table, Anthropic cost, dry-run output, screenshot of staging API showing NCP data

**Acceptance:**
- PR merged to `staging`
- Railway server deploy green on F1.1 migration
- Script run on Dars staging succeeds; all expected row counts present
- Aisha demo path unchanged (regression smoke: `GET /api/v2/today` on demo CST returns identical lessons to pre-change)
- `scripts/import_books.py` deleted; nothing else references it (verified via `git grep import_books`)
- ONRAMP.md updated: Current state shows feature ✅ Closed
- `docs/features/README.md` moves the feature from Active → Closed

**Dependencies:** F1.8 (and chronologically: PR merge + Railway deploy must precede script run).

---

## Phase exit checklist

- [ ] All 9 features merged in the bundled PR to `staging`
- [ ] Railway server deploy green; F1.1 migration applied
- [ ] Script run on Dars staging succeeds; counts logged
- [ ] Staging `/api/v2/curriculums/NCP/...` endpoints return NCP data
- [ ] Aisha demo path unchanged (`/api/v2/today` for demo CST still returns expected lessons)
- [ ] `scripts/import_books.py` removed
- [ ] ONRAMP.md Current State + feature ✅ Closed
- [ ] `docs/features/README.md` moved entry to Closed
- [ ] Phase 1 bead closed with resolution summary
