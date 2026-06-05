# Glossary — Core Book Import

Future docs may only use terms defined here. Add new terms as they emerge.

- **taleemabad-core / core** — the Django monolith's database. Accessed here via the
  `fde_staging` schema (SLO + book library tables). Read-only from Dars.
- **Core Book** — a row in `fde_staging.book_library_book`. Identified by an integer
  `id` (e.g. 1171). Carries `book_text` (JSONB page array), status, and joins to a
  grade + subject via `slo_gradesubject`.
- **Curriculum Cell** — the (curriculum, grade, subject) tuple a book belongs to. For
  core books the grade + subject come from the core row; the curriculum is chosen at
  import time (defaults to the active Dars curriculum). All imported rows are scoped
  to this cell.
- **Import** — the full ETL that materialises one Core Book's curriculum cell into Dars:
  SLOs, sub-SLOs, book + chapters, topics, and the mapping tables. Idempotent (upserts).
- **Import Run** — one execution of an Import, tracked by a row in the new `import_runs`
  table. Has a status, per-step progress, row counts, and an optional error.
- **Step** — a named stage of an Import: `slos`, `sub_slos`, `book_chapters`, `topics`,
  `mappings`. Progress is reported per step.
- **book_text** — JSONB array of page objects `[{pdf_page_no, text, page_type, …}]` on
  a Core Book; the canonical prose source. Copied verbatim into Dars `books.book_text`.
- **chapter_text** — the slice of `book_text` whose `pdf_page_no` falls in a chapter's
  `[start_page, end_page]`, stored on Dars `book_chapters.chapter_text`.
- **topic_text** — the prose stored on a Dars `topics` row. In this version, = the
  chapter's `chapter_text` pages flattened (1 topic per chapter). See [[D-3]].
- **Sub-SLO breakdown** — the LLM step that expands a top-level SLO into sub-SLOs, using
  Schema's breakdown prompt. The prompt is **vendored into the Dars repo** so it runs on
  Railway (the script read it from a workstation path — see [[D-4]]).
- **lp_type classifier** — the Claude step assigning each sub-SLO one of the 5 lp_type
  enum values (`scripts/lp_type_classifier.py`), ported into the service.
- **Already-imported** — a Core Book whose Dars rows already exist (matched by the
  deterministic `book:<curr>:<grade>:<subj>:<core_id>` UUID). The browse list flags this;
  re-import is allowed (upserts) but surfaced as an update, not a create.
