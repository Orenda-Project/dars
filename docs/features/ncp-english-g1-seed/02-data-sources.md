# Data Sources

For each piece of data the seed needs, this doc records: where it comes from, the source's shape, how the script extracts it, and which Dars table it lands in. Per D-18, the script writes **directly to Dars staging** via SQL upserts in a single transaction — there is no JSON intermediate.

---

## 1. NCP curriculum lookup row

| | |
|---|---|
| **Source** | hand-authored constant in the script |
| **Dars target** | `curriculums` table — one new row |
| **Shape** | `code='NCP'`, `label='National Curriculum of Pakistan'` |
| **Upsert** | `INSERT INTO curriculums (id, code, label) VALUES (<uuid5("curriculum:NCP")>, 'NCP', 'National Curriculum of Pakistan') ON CONFLICT (code) DO NOTHING` |
| **Notes** | UUID derived deterministically from a stable seed namespace, mirroring how `seeds/lookups.py` derives existing curriculum UUIDs. See `D-8`. |

---

## 2. Top-level NCP SLOs (English × Grade 1)

| | |
|---|---|
| **Source** | Live `fde_staging` schema → `fde_staging.slo_ncpslo` table, via read-only SQL |
| **Filter** | `grade_subject` where `grade.short_code = 'G1'` AND `subject.short_code = 'Eng'`; `slo_ncpslo.is_active = TRUE` |
| **Fields read** | `ncp_slo_id` (code, e.g. `A1-02`), `slo_statement`, `category` |
| **Fields ignored** | `domain`, `language_skills` — per `D-11`, those are not used; `lp_type` lives on sub-SLOs |
| **Dars target** | `slos` table |
| **Upsert** | `INSERT INTO slos (id, curriculum_id, grade_id, subject_id, code, statement, position) VALUES (uuid_generate_v4(), <ncp_uuid>, <g1_uuid>, <eng_uuid>, <ncp_slo_id>, <slo_statement>, <ordinal>) ON CONFLICT (curriculum_id, grade_id, subject_id, code) DO UPDATE SET statement = EXCLUDED.statement, updated_at = NOW()` |
| **Position** | Derived from row order sorted by `ncp_slo_id`. Position is stable across re-runs because the source set + sort order are stable. |

Extraction step (`scripts/import_ncp_english_g1.py::import_ncp_slos`):
1. Use the read-only fde_staging connection (set up in F1.3)
2. Run the join + filter above
3. For each row, upsert into Dars `slos`
4. Collect a `{ncp_slo_id: dars_slo_uuid}` map; pass to F1.6 so sub-SLOs can find their parent

---

## 3. Sub-NCP-SLOs

| | |
|---|---|
| **Source** | Schema's breakdown service — `/home/hataf/taleemabad/Schema/services/slo_mapping.py::get_sub_ncp_slos_for_mapping(grade_label="Grade One", subject_key="english")`. LLM-backed. |
| **Filter** | Implicit — Schema's function scopes to (grade, subject). Output is parsed sub-SLO markdown rows. |
| **Fields read** | `Sub SLO Code` (e.g. `A1-02-a`), `Sub SLOs` (statement) |
| **Derived** | `parent_slo_code` via code prefix (`A1-02-a` → `A1-02`); `lp_type` via Claude classifier (§3a) |
| **Dars target** | `sub_slos` table |
| **Upsert** | `INSERT INTO sub_slos (id, slo_id, code, statement, position, source, recommended_lp_type) VALUES (uuid_generate_v4(), <parent_slo_uuid>, <code>, <statement>, <ordinal>, 'schema_breakdown', <lp_type>) ON CONFLICT (slo_id, code) DO UPDATE SET statement = EXCLUDED.statement, recommended_lp_type = EXCLUDED.recommended_lp_type, position = EXCLUDED.position, updated_at = NOW()` |
| **Position** | Ordinal within parent SLO (1, 2, 3, … per `a`, `b`, `c`, …) |
| **`recommended_lp_type` column** | Added by F1.1's migration. See `D-12`. |

Extraction step:
1. Import Schema's `slo_mapping` module (or invoke via subprocess if env conflict)
2. Call `get_sub_ncp_slos_for_mapping(grade_label="Grade One", subject_key="english", force_refresh=False)`
3. Save the returned `breakdown_markdown` to `/tmp/<timestamp>_breakdown_markdown.md` for ad-hoc audit (not committed)
4. Parse rows into `{code, statement, parent_slo_code}` records
5. **Pass each record through the Claude lp_type classifier (§3a) to populate `lp_type`**
6. Upsert each into Dars `sub_slos`

If Schema requires an LLM key, the developer running the script must have it. See `D-9`.

---

## 3a. Claude lp_type classifier (per sub-SLO)

Per `D-11` and `D-14`. Runs as part of §3 step 5.

| | |
|---|---|
| **Source code** | `dars/scripts/lp_type_classifier.py` — uses Anthropic SDK directly |
| **Input** | a sub-SLO `{code, statement, parent_slo_statement}` |
| **Output** | one of `{reading, comprehension_word_meanings, comprehension_qa, grammar, creative_writing}` |
| **Model** | `claude-haiku-4-5-20251001` |
| **Prompt caching** | the 5-value enum description + few-shot examples are a single cached system block; each per-sub-SLO classification reuses it. Reduces cost by ~90% across the ~70+ sub-SLOs of English G1. |
| **Determinism** | `temperature=0`. Re-running against the same sub-SLO returns the same lp_type. |
| **Fallback** | if Claude returns a value outside the enum, classifier retries once with stricter prompt; second failure raises. No silent default. |

Classifier prompt structure (kept short for cache stability):

```
[CACHED SYSTEM]
You classify English-language sub-learning-outcomes into one of 5 lesson-plan types.
Valid values: reading | comprehension_word_meanings | comprehension_qa | grammar | creative_writing
[short definitions + 1 example per type]

[PER-REQUEST USER]
Parent SLO: <statement>
Sub-SLO: <statement>
Return only the enum value, no explanation.
```

---

## 4. Book + chapters + chapter prose

**Scope:** exactly one book — `fde_staging.book_library_book.id = 1171`, "English G1 Taleemabad" by Taleemabad publisher, status OnProd, category HYPER_SPECIFIC. See `D-15`. Script accepts `--book-id` so the same code can be re-used for other books later (idempotent upserts make re-running safe).

| | |
|---|---|
| **Source — book metadata** | `fde_staging.book_library_book` row where `id = 1171` |
| **Source — book prose** | `book.book_text` JSONB on the same row — a flat array of 169 page objects: `{text, page_type, pdf_page_no, book_page_no, pdf_page_image_url}`. **This is the canonical source of prose.** |
| **Source — chapter index** | `fde_staging.book_library_bookchapter` rows where `book_id = 1171`, ordered by `chapter_number`. **No `is_active` filter** — all 12 chapter rows are used (D-16). Chapter table contributes chapter_number, title, start_page, end_page only; its own `chapter_text` field is ignored. |
| **Per-chapter prose** | For each chapter row, slice `book.book_text` to elements where `pdf_page_no BETWEEN start_page AND end_page`. Resulting prose is the concatenation of those pages' `text` fields (or the raw JSON sub-array — choice made at script-impl time; logged in execution notes). |
| **Sanity assert** | Before reading: book row must have `status='OnProd'`, `is_active=TRUE`, joined grade='G1', subject='Eng'. If mismatched, raise immediately — prevents seeding wrong book by accident. |
| **Dars target — book** | `books` table |
| **Dars target — chapters** | `book_chapters` table |
| **Upsert (book)** | `INSERT INTO books (id, curriculum_id, grade_id, subject_id, title, publisher, edition, published_year, total_chapters, pdf_url, book_text) VALUES (...) ON CONFLICT (curriculum_id, grade_id, subject_id, title) DO UPDATE SET book_text = EXCLUDED.book_text, total_chapters = EXCLUDED.total_chapters, ..., updated_at = NOW()` (book unique-key may need confirming against current schema; see F1.7 acceptance) |
| **Upsert (chapter)** | `INSERT INTO book_chapters (id, book_id, chapter_number, title, start_page, end_page, chapter_text, status) VALUES (...) ON CONFLICT (book_id, chapter_number) DO UPDATE SET ...` |
| **Chapter `status`** | `'published'` for OnProd-source rows, `'draft'` for the 4 stub source rows (chapters 2, 5, 7, 10). The Dars v2 `book_chapters.status` column accepts this enum per the v2 schema. |
| **Stub titles** | "chapter 5", "chapter 7" etc. are passed through as-is. Fix in fde_staging if needed; not the script's job. |
| **Status filter on book** | `book.status = 'OnProd'` — mixed-case, **not** `ON_PROD`. Verified against live fde_staging. |

---

## 5. Topics

| | |
|---|---|
| **Source (preferred)** | Schema's topic-extraction output for English G1 chapters |
| **Source (fallback)** | One synthetic topic per chapter, logged at INFO. See `D-7`. |
| **Fields per topic** | `topic_number` (order within chapter), `title`, `text` (prose) |
| **Dars target** | `topics` table |
| **Upsert** | `INSERT INTO topics (id, book_chapter_id, topic_number, title, text) VALUES (...) ON CONFLICT (book_chapter_id, topic_number) DO UPDATE SET title = EXCLUDED.title, text = EXCLUDED.text, updated_at = NOW()` |
| **Synthetic-fallback tracking** | Topics that are fallbacks are logged with the chapter number; counts go into the PR description. No flag column on `topics` (the schema doesn't have one; the audit trail is the script log + PR body). |

---

## 6. Topic ↔ sub-SLO mappings

| | |
|---|---|
| **Source** | Schema's `map_topics_to_ncp_slos` (in `Schema/services/chapter_plan.py`). LLM-backed. |
| **Filter** | English G1 only — chapters passed in from §5 |
| **Fields per mapping** | `topic_id` (from §5 upsert return), `sub_slo_id` (from §3 upsert return, looked up by code) |
| **Dars target — topics ↔ sub_slos** | `topic_sub_slos` (linking table) |
| **Dars target — chapters ↔ slos** | `book_chapter_slos` (derived: union of parent SLOs of the chapter's topics' sub-SLOs) |
| **Upsert** | `INSERT INTO topic_sub_slos (topic_id, sub_slo_id) VALUES (...) ON CONFLICT (topic_id, sub_slo_id) DO NOTHING` |
| **Integrity** | Every `sub_slo_id` referenced must exist in `sub_slos` (FK enforces; script also asserts in-Python before INSERT for clearer errors) |

---

## Script

Lives at `dars/scripts/import_ncp_english_g1.py`. Reads three sets of env vars:
- `CORE_STAGING_DB_HOST/PORT/NAME/USER/PASSWORD` — read-only fde_staging access (D-17)
- `DARS_STAGING_DATABASE_URL` — read-write Dars staging access (D-19)
- `ANTHROPIC_API_KEY` — for the Claude lp_type classifier (D-11, D-14)

Plus whatever Schema's internal LLM calls need (Schema reads its own env).

CLI: `--book-id <int>` (defaults `1171`), `--dry-run` (skip the COMMIT; log what would change), `--verbose`.

All writes happen in a **single Dars transaction**:

```python
async with dars_conn.transaction():
    curriculum_id = await upsert_ncp_curriculum_row(dars_conn)
    slo_map = await import_ncp_slos(dars_conn, fde_conn, curriculum_id)
    sub_slo_map = await import_sub_slos(dars_conn, slo_map)
    chapters = await import_book_and_chapters(dars_conn, fde_conn, book_id, curriculum_id)
    await import_topics_and_mappings(dars_conn, chapters, sub_slo_map)
```

On any error: transaction rolls back, exits non-zero. On success: transaction commits, exits zero with a summary of row counts and Claude cost.

Per `D-9`, this runs on a developer workstation — not on Railway.

---

## What is NOT touched

- Lesson plans — LP Assistant generates on demand
- Teacher / org / class data — Aisha demo stays (D-4)
- Curriculum/grade/subject lookup completeness — already real
- Existing Dars curriculum SLOs / books — untouched (D-4)
- `v2_seed.py` runtime boot seed — no changes (D-18)
- Any data outside the (NCP, English, G1) cell
