# Reference — the proven ETL (`scripts/import_ncp_english_g1.py`)

Frozen extract of the script the import **service ports**. The service generalises the
hard-coded `NCP/G1/Eng` to the resolved cell (D-2, D-6) and vendors the prompt (D-4),
but the per-step logic below is the source of truth — port it, don't reinvent it.

## Connections (script → service)

- Core: `asyncpg.connect(core_dsn)` then `SET search_path TO fde_staging, public`,
  read-only. Service uses `settings.effective_core_db_url` (D-5/D-7).
- Dars: `asyncpg.connect(dars_dsn)`, all writes in **one transaction**
  (`async with dars_conn.transaction(): …`). Service opens its own connections in the
  background task (D-5).

## Step `slos` — `import_ncp_slos`

Read from core:
```sql
SELECT n.ncp_slo_id, n.slo_statement, n.category
FROM fde_staging.slo_ncpslo n
JOIN fde_staging.slo_gradesubject gs ON n.grade_subject_id = gs.id
JOIN fde_staging.slo_grade g ON gs.grade_id = g.id
JOIN fde_staging.slo_subject s ON gs.subject_id = s.id
WHERE g.short_code = $1 AND s.short_code = $2 AND n.is_active = TRUE
ORDER BY n.ncp_slo_id
```
(script hard-codes `'G1'`/`'Eng'`; service passes the resolved cell's short codes.)
Upsert each into Dars `slos` with `position` = row ordinal, UUID `slo:<CURR>:<GR>:<SUBJ>:<code>`.
Returns `{code: (uuid, statement)}`.

## Step `sub_slos` — `import_sub_slos`

1. Render the SLO list into the breakdown prompt's expected shape.
2. **One** Anthropic call with the vendored breakdown system prompt (D-4) → markdown table.
   Model: Opus (script uses opus for breakdown). Save raw markdown to a temp/audit log.
3. Parse markdown rows → `{code, statement, parent_slo_code}` (`_parse_breakdown_markdown`,
   inlined — tolerant of header/summary lines).
4. For each row: derive `parent_slo_code` by code prefix; run the **lp_type classifier**
   (`scripts/lp_type_classifier.py`, Claude Haiku, temp 0, 5-value enum, cached system
   block, retry-once-then-raise) → `recommended_lp_type`.
5. Upsert into Dars `sub_slos` (`source='schema_breakdown'`), UUID
   `sub_slo:<CURR>:<GR>:<SUBJ>:<code>`. Returns `{code: uuid}`.

Note (D-4): the breakdown prompt is English-specific. Non-English cells either reuse it
or need their own prompt file; log a warning if no subject-specific prompt exists.

## Step `book_chapters` — `import_book_and_chapters`

Read book row from core (`book_library_book` joined to grade/subject). Service **does
not** assert G1/Eng (D-2) — it asserts `status='OnProd'`, `is_active`, and that the core
grade/subject `short_code`s resolve to Dars lookups. Parse `book_text` JSONB (asyncpg may
return str). Upsert Dars `books` (book_text verbatim), UUID `book:<CURR>:<GR>:<SUBJ>:<core_id>`.

Read chapters: `book_library_bookchapter WHERE book_id=$1 AND deleted_at IS NULL ORDER BY
chapter_number` (no is_active filter). For each, slice `book_text` to pages with
`start_page ≤ pdf_page_no ≤ end_page` → `chapter_text` JSONB; upsert Dars `book_chapters`
(`status` 'published'/'draft' mirroring source), UUID `book_chapter:…:<chapter_number>`.
Chapters with null page range → empty slice + a `warnings[]` entry. Returns chapter list.

## Step `topics` + `mappings` — `import_topics_and_mappings` (D-3)

For each chapter:
- Re-read the chapter's `chapter_text` from Dars; `prose = _flatten_chapter_prose(...)`
  = `"\n\n".join(page["text"])`.
- Upsert **one** `topics` row (`topic_number=1`, `title`=chapter title,
  `topic_text=prose[:50000]`), UUID `topic:…:ch<n>:1`.
- If prose non-empty: **one** Anthropic call mapping the chapter prose to applicable
  sub-SLO codes (`_map_chapter_to_sub_slos`, cached sub-SLO index system block, validates
  returned codes against the known set). Upsert `topic_sub_slos` (topic↔sub-SLO) and,
  derived, `book_chapter_slos` (chapter↔parent-SLO union). Empty prose → warning, skip mapping.

## Counts + warnings

The service records per-step counts into `import_runs.counts` and non-fatal notes into
`import_runs.warnings` (chapters with no page range, chapters skipped for empty prose,
sub-SLO rows dropped as malformed). On any exception: roll back the Dars transaction, set
`status='failed'` + `error`, and persist the run row (the run-row write is **not** inside
the rolled-back transaction).
