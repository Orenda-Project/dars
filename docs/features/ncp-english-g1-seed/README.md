# NCP English G1 Seed

Add real-curriculum data alongside the existing synthetic Dars seed. Scope: **NCP curriculum × English × Grade 1** only — mirrors the current `Dars × English × G1` cell. The Aisha + G1-A demo tenancy is unchanged.

A **one-shot Python script** runs locally on a developer workstation. It reads from `fde_staging` (live taleemabad-core SLO + book tables) and Schema (LLM-backed sub-SLO breakdown + topic mapping) and Claude (sub-SLO `lp_type` classification), then **writes directly to Dars staging via SQL upserts** in a single transaction. No JSON intermediate, no runtime seed integration, no Phase 2.

## Why this feature exists

The existing seed is hand-authored synthetic content. To validate the v2 rebuild against realistic curriculum shapes (real SLO counts, real book structure, real prose), we need actual NCP data in staging. Doing this without disturbing the Dars demo lets us keep all current tests + screenshots stable while a parallel real-data path comes online.

## Files in this folder, in read order

1. **`README.md`** — this index
2. **`00-glossary.md`** — terminology specific to NCP data shapes
3. **`01-decision-log.md`** — frozen architectural decisions for this feature (`D-1`, `D-2`, …) including supersessions (D-2→D-11, D-3→D-18, D-10→D-12)
4. **`02-data-sources.md`** — where each piece of data comes from + how the script writes it to Dars
5. **`03-phase-1.md`** — sole phase: migration + heuristic updates + script + run + close-out PR

## Document precedence (if two docs disagree, top wins)

```
1. 01-decision-log.md         (D-N references are canonical)
2. 02-data-sources.md         (extraction approach is ground truth)
3. 00-glossary.md             (terminology)
4. phase docs (03, 04)        (specs derived from above)
5. running code               (last; code may be stale)
```

Code is **lowest** authority. Surface conflicts; don't silently pick a side.

## Scope summary

One script (`dars/scripts/import_ncp_english_g1.py`) does the whole import. Runs once on a developer workstation. Connects read-only to `fde_staging` (creds from `CORE_STAGING_DB_*`) and read-write to Dars staging (creds from `DARS_STAGING_DATABASE_URL`). All writes happen in a single transaction.

| Dars table | Source | Mechanism |
|---|---|---|
| `curriculums` (new `NCP` row) | hand-authored constant in the script | `INSERT … ON CONFLICT DO NOTHING`, deterministic UUID |
| `slos` | **`fde_staging.slo_ncpslo`** joined to `slo_gradesubject` etc., filtered English × G1 + `is_active=TRUE` | `INSERT … ON CONFLICT (curriculum_id, grade_id, subject_id, code) DO UPDATE` |
| `sub_slos` | **Schema breakdown service** (LLM-backed) → for each sub-SLO, **Claude classifier** assigns `lp_type` | `INSERT … ON CONFLICT (slo_id, code) DO UPDATE` |
| `books` | **`fde_staging.book_library_book` where `id = 1171`** (D-15) — pulls metadata + `book_text` JSONB | `INSERT … ON CONFLICT (curriculum_id, grade_id, subject_id, title) DO UPDATE` |
| `book_chapters` | **`fde_staging.book_library_bookchapter` where `book_id = 1171`**, all 12 rows, no `is_active` filter; per-chapter prose sliced from `book.book_text` on `pdf_page_no` (D-16) | `INSERT … ON CONFLICT (book_id, chapter_number) DO UPDATE` |
| `topics` | **Schema's topic extraction** — fallback synthetic-per-chapter per D-7 | `INSERT … ON CONFLICT DO UPDATE` |
| `topic_sub_slos` | **Schema's `map_topics_to_ncp_slos`** | `INSERT … ON CONFLICT DO NOTHING` |
| `book_chapter_slos` | derived from topic mappings (chapter ↔ SLO via topics) | `INSERT … ON CONFLICT DO NOTHING` |

**Not touched by this feature:**

- Lesson plans (LP Assistant generates on-demand)
- Tenancy (Aisha + G1-A demo stays)
- Existing Dars curriculum SLOs/books (untouched per D-4)
- `v2_seed.py` (no changes — runtime boot seed is unchanged)

## What this feature does NOT do

- Does not change Dars curriculum seed (synthetic Dars × English × G1 stays as-is)
- Does not change demo tenancy (org / school / AY / class / teacher)
- Does not seed lesson plans (LP Assistant generates them)
- Does not add new (curriculum × grade × subject) cells beyond `NCP × English × G1`
- Does not touch production
- Does not modify `v2_seed.py` — no runtime boot seed integration
- Does not produce JSON fixtures — the script writes directly to Dars staging

The feature **does** add one column to the v2 schema: `sub_slos.recommended_lp_type TEXT NULL` (per D-12). That's a small additive migration, applied via Railway deploy in the same PR.
