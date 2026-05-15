# Phase 1: Foundation

**Goal:** New data model on staging, fully seeded with believable Dars Curriculum + English G1 content, with read-only API endpoints to inspect everything.

**Bead:** `feat-v2-phase-1-foundation` (open at start, close on staging green).

**Pre-reqs:** none.

**Deliverables:**
- Staging DB dropped and recreated under the v2 schema (D-34)
- Seed loaded (Dars Curriculum, English G1, 1 org, 1 school, 1 class, 1 teacher, 1 CST)
- Read-only API endpoints for every entity in the new schema
- Smoke test that fetches the entire seed via the API

**NOT in this phase:** write endpoints, FE changes, generation pipeline, breakdown engine. Just data model + read API.

---

## Feature order

1. **F1.1** — Migration: drop everything, create v2 schema
2. **F1.2** — Lookup seed (grades, subjects, curriculums)
3. **F1.3** — Dars Curriculum English G1 seed: SLOs + sub-SLOs
4. **F1.4** — Dars Curriculum English G1 seed: Book + Chapters + Topics + mappings
5. **F1.5** — Tenancy seed: Org, School, AcademicYear, Class, Teacher, CST, timetable
6. **F1.6** — Read-only API: tenancy entities
7. **F1.7** — Read-only API: curriculum entities
8. **F1.8** — Read-only API: book / chapter / topic entities
9. **F1.9** — Seed smoke test (end-to-end fetch via API)
10. **F1.10** — Cleanup: delete old code paths (clients table router, old service.py functions etc) that don't compile

---

## F1.1 — Migration: drop everything, create v2 schema

**Motivation:** Existing schema is incompatible. Start fresh on staging.

**Spec:**
- File: `server/src/dars/migrations/20260516000000_v2_cutover.sql`
- Contents:
  1. `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` (clean slate; preserves Supabase extensions in `extensions` schema)
  2. `CREATE EXTENSION IF NOT EXISTS pgcrypto;` (for `gen_random_uuid()`)
  3. CREATE TABLE statements for every table in `02-data-model.md` Section 1-8, in the order listed in Section 10
- Migrations run automatically on Railway deploy (Critical Rule #7) — do not run manually.
- For local dev: `make migrate` runs them via Supabase CLI against local Postgres.

**Test plan:**
- Migration file is valid SQL (no syntax errors); `psql --set ON_ERROR_STOP=on` against a fresh local DB applies cleanly.
- All tables listed in 02-data-model.md exist after migration.
- All indexes from Section 11 exist.

**Acceptance:**
- Migration applied to staging successfully via Railway deploy
- `psql -c "\dt"` shows all tables; `psql -c "\di"` shows all indexes
- Existing dars test suite removed or marked skip (D-19); a new smoke test (F1.9) replaces it

---

## F1.2 — Lookup seed: grades, subjects, curriculums

**Motivation:** These tables hold global enum-like data, must exist before any other seed.

**Spec:**
- File: `server/src/dars/seeds/v2_seed.py` (one file, top-level `async def main()` that runs the whole seed in dependency order)
- This feature seeds the lookup tables only; later features extend the same file
- **Grades:** insert rows for grades 1–12 with `(code=N, display_name='Grade {N}')`
- **Subjects:** insert rows matching LP Assistant + UG_EG support (codes: `Eng`, `Urdu`, `Maths`, `Science`, `GK`, `Islamiat`, `GenSci`, `SST`)
- **Curriculums:** insert `Dars Curriculum` (code=`DARS`, name=`Dars Curriculum`, active=True). Also insert `NCP` and `SNC` as inactive placeholders for future seed.
- Seed is idempotent: use `INSERT ... ON CONFLICT DO NOTHING` keyed on the unique columns (`grades.code`, `subjects.code`, `curriculums.code`)
- Run with: `make seed` → `python -m dars.seeds.v2_seed`

**Test plan:**
- Run seed against fresh DB; verify row counts (12 grades, 8 subjects, 3 curriculums)
- Run seed twice; verify idempotent (no errors, no dupes)

**Acceptance:**
- Seed script runs in <5s on local
- All lookup IDs are stable (don't randomize for the seed; use deterministic UUIDs via `uuid5(NAMESPACE_OID, 'grade:1')` etc., so test fixtures can reference them)

---

## F1.3 — Dars Curriculum English G1 seed: SLOs + sub-SLOs

**Motivation:** SLOs are the unit of truth (D-A1). Without them, nothing downstream works.

> 🧊 **SEED FREEZE RULE:** The seed produced in F1.3 + F1.4 + F1.5 is authored **once**, reviewed by the user, and committed as `server/src/dars/seeds/v2_seed.py`. After commit, the seed is frozen — Phase 2+ features reference specific SLO codes, topic IDs, and book chapter numbers that come from this seed. **Do not regenerate the seed in later phases** without explicit user approval. If a fact needs to change (typo, addition), edit the seed file directly, get user approval, and note in the decision log as a "seed amendment" with date and reason.

**Spec:**
- Extend `v2_seed.py`
- Author ~25 SLOs for English Grade 1 in Dars Curriculum, organized into 5 conceptual areas (reading, writing, listening, speaking, grammar). Use codes like `R1-01`, `W1-01`, `L1-01`, `S1-01`, `G1-01`.
- For each SLO, author 3-5 sub-SLOs (target ~100 sub-SLOs total). Use codes like `R1-01-a`, `R1-01-b`.
- Source these from Pakistani early-grades English standards I know (Single National Curriculum 2020 English Grade 1, NCP English Grade 1). Don't claim they're "official" — they're plausible for a v1 demo seed.
- All sub-SLOs have `source='manual'` for now (Schema-generated sub-SLOs in later phases use `source='schema_breakdown'`).
- Insert idempotently keyed on `(curriculum_id, grade_id, subject_id, code)`.

**Concrete sample of what to seed (NOT exhaustive — full list lives in the seed file):**

```
R1-01: Student can identify and name all 26 letters of the English alphabet
  R1-01-a: Identifies uppercase letters A-Z
  R1-01-b: Identifies lowercase letters a-z
  R1-01-c: Matches uppercase to lowercase letters

R1-02: Student can read CVC words (consonant-vowel-consonant)
  R1-02-a: Reads CVC words with short 'a' sound (cat, hat, man)
  R1-02-b: Reads CVC words with short 'e' sound (bed, hen, pen)
  R1-02-c: Reads CVC words with short 'i', 'o', 'u' sounds
  R1-02-d: Blends individual sounds into a word
  
W1-01: Student can write all 26 letters of the alphabet with correct formation
  W1-01-a: Writes uppercase letters with correct strokes
  W1-01-b: Writes lowercase letters with correct strokes
  W1-01-c: Maintains letter size proportional to lines on paper

[... ~22 more SLOs across reading, writing, listening, speaking, grammar ...]
```

**Test plan:**
- After seed, query `SELECT COUNT(*) FROM slos WHERE curriculum_id = (SELECT id FROM curriculums WHERE code='DARS') AND grade_id = (SELECT id FROM grades WHERE code=1) AND subject_id = (SELECT id FROM subjects WHERE code='Eng')` → expect ~25
- Same for sub-SLOs → expect ~100

**Acceptance:**
- The full SLO + sub-SLO list reads sensibly to a teacher (review by user)
- All sub-SLOs have a parent SLO; no orphans

---

## F1.4 — Dars Curriculum English G1 seed: Book + Chapters + Topics + mappings

**Motivation:** The book is the source of `page_content` we feed LP Assistant. Need believable content.

**Spec:**
- Extend `v2_seed.py`
- **Book:** "Dars English Grade 1 Reader," publisher "Dars Press," ~70 pages, 10 chapters.
- **Chapters:** 10 chapters, each ~6-8 pages, sensibly themed for Pakistani G1:
  1. Hello, World (greetings + letters A-E)
  2. My Family (family vocabulary + introducing yourself)
  3. School Time (classroom words + simple sentences)
  4. The Clever Crow (a short fable + comprehension)
  5. Numbers and Letters (CVC words + number words)
  6. Colors and Things (color words + adjectives)
  7. My Body (body parts + commands)
  8. Animals Around Us (animal names + descriptive sentences)
  9. The Three Friends (a story + simple grammar)
  10. Review and Practice (revision unit)
- **OCR'd text (`book_text` JSONB):** for each chapter, write ~300-500 words of grade-appropriate English content. This is hand-authored, formatted as `[{pdf_page_no, text}, ...]`. The text should look like a real OCR pass: numbered pages, occasional small inconsistencies, but readable.
- **Chapter text (`chapter_text` JSONB):** populate by slicing `book_text` per chapter's page range. Run at seed time so this is precomputed.
- **Topics:** for each chapter, define 3-4 topics with line-number boundaries within `chapter_text`. E.g. Chapter 1 has topics: "Greetings", "Letters A-E", "Practice".
- **`topic_text`:** populated by joining the lines in the topic's range.
- **`book_chapter_slos`:** each chapter linked to 3-5 SLOs (the chapter "teaches" these).
- **`topic_sub_slos`:** each topic linked to 2-5 sub-SLOs (granular).
- **Chapter and topic status:** all set to `published` (seed is final, not draft).

**Test plan:**
- `book_text` is non-empty for the book; concatenated chapter_text totals approximately match book_text
- Every chapter has at least one topic
- Every topic has at least one sub-SLO mapping
- Every SLO has at least one chapter teaching it (no orphan SLOs in the seed)

**Acceptance:**
- A read of the book_text by a human is convincingly G1 English material
- Topic boundaries don't break mid-sentence
- The SLO coverage spans all 25 SLOs (no SLOs untaught by the book)

---

## F1.5 — Tenancy seed: Org, School, AY, Class, Teacher, CST, timetable

**Motivation:** Need a fully wired-up CST so later phases can attach breakdowns and slots to it.

**Spec:**
- Extend `v2_seed.py`
- **Organization:** name "Dars Demo Org", curriculum_id = Dars Curriculum, generate an API key (store its SHA-256 hash + print the raw key on first seed run — devs save it)
- **OrgAdmin:** name "Demo Admin", email "demo@dars.local", password "demo1234" (bcrypt hash). v1 quality.
- **School:** "Dars Demo School" under the org
- **AcademicYear:** "2026-2027" under the school, start 2026-04-01, end 2027-03-31 (typical Pakistani academic year)
- **Teacher:** name "Aisha Khan", email NULL, under the school
- **SchoolClass:** "Grade 1 - A" (grade=1, section="A"), under AY 2026-2027
- **CST:** teacher=Aisha, class=Grade 1-A, subject=Eng, book=Dars English Grade 1 Reader. Set Org's `default_teacher_id` to Aisha.
- **Timetable:** Mon-Fri (day_of_week 0..4) for the CST
- **CSTState:** current_sequence_position=1, joined_at_position=1

**Test plan:**
- API key works against future endpoints
- `GET /api/v1/me/classes` returns this CST (in a later phase)
- No FK violations

**Acceptance:**
- Seed produces stdout output including the raw API key for first-time setup
- All IDs are deterministic (uuid5 from "{org_name}:{name}") so tests can hard-reference

---

## F1.6 — Read-only API: tenancy entities

**Motivation:** Foundation for everything; lets us inspect seed and lets future phases query.

**Spec:** Endpoints under `/api/v1/`:

| Method | Path | Description |
|---|---|---|
| GET | `/orgs/me` | The org owning the request's API key |
| GET | `/schools` | List schools for the org |
| GET | `/schools/{id}` | Single school |
| GET | `/teachers` | List teachers (filter by `?school_id=`) |
| GET | `/teachers/{id}` | Single teacher |
| GET | `/academic-years` | List AYs (filter by `?school_id=`) |
| GET | `/academic-years/{id}` | Single AY |
| GET | `/classes` | List classes (filter by `?school_id=`, `?academic_year_id=`, `?grade_id=`) |
| GET | `/classes/{id}` | Single class |
| GET | `/csts` | List CSTs (filter by `?school_class_id=`, `?teacher_id=`) |
| GET | `/csts/{id}` | Single CST with computed fields (e.g. `current_sequence_position`) |

All endpoints require API key auth (existing pattern). All filter by `org_id` (Critical Rule #3).

Pydantic response schemas per `02-data-model.md`. UUIDs serialized as strings.

**Test plan:**
- One integration test per endpoint: hit it with the seed's API key, assert response shape and content matches the seed
- One negative test: hit with another org's API key (or fabricated org), assert empty/404

**Acceptance:**
- All endpoints documented in OpenAPI (auto-generated)
- Tests passing

---

## F1.7 — Read-only API: curriculum entities

**Motivation:** Inspect SLOs, sub-SLOs, etc. Foundation for breakdown UI.

**Spec:**

| Method | Path | Description |
|---|---|---|
| GET | `/curriculums` | All active curriculums |
| GET | `/curriculums/{id}` | Single curriculum |
| GET | `/grades` | All grades |
| GET | `/subjects` | All subjects |
| GET | `/slos` | List SLOs (filter by `?curriculum_id=`, `?grade_id=`, `?subject_id=`) |
| GET | `/slos/{id}` | Single SLO with embedded sub_slos array |
| GET | `/sub-slos` | List sub-SLOs (filter by `?slo_id=`) |
| GET | `/sub-slos/{id}` | Single sub-SLO |

Curriculum/grade/subject endpoints are public (no auth — they're global enums). SLOs+sub-SLOs are public too (the curriculum is global; no org-scoped filtering needed).

**Test plan:**
- Hit `/slos?curriculum_id=DARS&grade_id=1&subject_id=Eng` → expect ~25 rows from seed
- Hit `/sub-slos?slo_id={any}` → expect 3-5 rows

**Acceptance:** tests passing, OpenAPI complete.

---

## F1.8 — Read-only API: book/chapter/topic entities

**Motivation:** Inspect the book, chapters, topics. Foundation for breakdown engine to query topics.

**Spec:**

| Method | Path | Description |
|---|---|---|
| GET | `/books` | List books (filter by `?curriculum_id=&grade_id=&subject_id=`) |
| GET | `/books/{id}` | Single book (omit book_text by default; `?include=book_text` to include) |
| GET | `/book-chapters` | List chapters (filter by `?book_id=`) |
| GET | `/book-chapters/{id}` | Single chapter (omit `chapter_text` by default; `?include=chapter_text` to include) |
| GET | `/book-chapters/{id}/slos` | SLOs taught by this chapter |
| GET | `/topics` | List topics (filter by `?book_chapter_id=`) |
| GET | `/topics/{id}` | Single topic (always include `topic_text` since it's small) |
| GET | `/topics/{id}/sub-slos` | Sub-SLOs taught by this topic |

**Test plan:**
- Hit each endpoint against seed, assert content
- Verify `book_text` and `chapter_text` exclusion default works (response payload is small without `include=...`)

**Acceptance:** tests passing.

---

## F1.9 — Seed smoke test (end-to-end fetch via API)

**Motivation:** One test that validates the entire phase: schema correct, seed loaded, endpoints work.

**Spec:**
- File: `server/tests/test_v2_seed_smoke.py`
- Single test function that:
  1. Resolves the seeded org by its (hardcoded test) API key
  2. Fetches schools, picks the demo school
  3. Fetches teachers under the school, finds Aisha
  4. Fetches CSTs, finds the Eng G1A CST
  5. Fetches the book referenced by that CST
  6. Fetches all chapters of that book; for each, fetches its SLOs and topics
  7. For each topic, fetches its sub-SLOs
  8. Asserts the shape matches the seed (e.g. exactly 10 chapters, 30+ topics, 100+ sub-SLOs)
- Run in CI on every PR (existing test pipeline)

**Test plan:** the test IS the test plan.

**Acceptance:** the smoke test passes on a fresh staging DB after running migration + seed.

---

## F1.10 — Cleanup

**Motivation:** Existing code references old tables (clients, etc.) that don't exist anymore. Must compile.

**Spec:**
- Delete: `server/src/dars/clients/` (replaced by `organizations`)
- Rename `clients` references to `organizations` throughout codebase, OR delete the old code outright if it isn't reused
- Delete tests that exercise dropped tables (D-19)
- Update any router import that breaks compile
- Ensure `make test` passes (against the new smoke test + nothing else for v2)

**Test plan:**
- `make test` exits 0
- `make run` starts the server cleanly

**Acceptance:**
- Backend compiles, server starts, smoke test passes, all old test files either updated or deleted

---

## Phase 1 wrap-up checklist

Before closing the bead and starting Phase 2:

- [ ] Migration applied to staging successfully (verify via Railway logs)
- [ ] Seed run on staging; raw API key captured (paste into 1Password or wherever the team stores demo keys)
- [ ] All read-only endpoints respond 200 with expected shape (manual smoke check)
- [ ] Smoke test passing on CI
- [ ] OpenAPI docs at `/docs` show all new endpoints
- [ ] No old `clients/` references compile-break

Open Phase 2 bead.
