# Decision log — Core Book Import

Indexed `D-1`, … Frozen. To revise: ask the user, mark old "Superseded by D-N on
YYYY-MM-DD", add the new referencing the supersession.

---

**D-1: Imports run as a background job tracked by an `import_runs` table; the dashboard
polls a status endpoint.** *Rationale:* the ETL does core reads + multiple LLM calls
(sub-SLO breakdown, per-sub-SLO lp_type, chapter→sub-SLO mapping) — tens of seconds to
minutes; a synchronous request would hit gateway/browser timeouts and block the admin.
*Apply:* `POST /api/v2/admin/book-imports` returns `202 {import_run_id}` and schedules a
FastAPI background task; `GET /api/v2/admin/book-imports/{id}` returns status + per-step
progress + counts + error; the frontend polls it. *Decided:* 2026-06-04 (user choice
"Background job + status polling").

**D-2: The admin browses Core Books; grade/subject are derived from the core row, not
entered.** *Rationale:* usability + correctness — the core row is the source of truth for
the book's grade/subject, so deriving them removes a class of mismatch errors and the
script's hard-coded `grade=='G1' AND subject=='Eng'` assertion. *Apply:* new
`GET /api/v2/admin/core-books` queries `fde_staging.book_library_book` joined to
grade/subject (filtered to `status='OnProd'`, `is_active=TRUE`, `deleted_at IS NULL`),
returns `{core_book_id, title, publisher, grade, subject, status, total_chapters,
already_imported}`. The import resolves the Dars grade_id/subject_id from the core
row's `short_code`s; the **curriculum is chosen at import** (defaults to the active Dars
curriculum). The G1/Eng assert is dropped; replaced by "the resolved grade/subject must
exist as Dars lookups" (else 422). *Decided:* 2026-06-04 (user choice "Browse core books,
auto-derive scope").

**D-3: Topics stay 1-per-chapter in this version; real per-topic breakdown is a logged
fast-follow.** *Rationale:* Schema's topic-extraction was never wired into the proven
script (it fakes 1 synthetic topic/chapter, `topic_text` = flattened chapter pages);
building real topic extraction is unproven, the riskiest part, and would expand scope.
Ship the proven behaviour now. *Apply:* the service ports the script's topic step
verbatim — one `topics` row per chapter, `topic_text` = `_flatten_chapter_prose(chapter_text)`
(truncated 50_000 chars), chapter mapped to sub-SLOs as a whole. Known limitation:
`topic_text` duplicates `chapter_text` (documented). Follow-up bead
`core-book-import-real-topics` (port Schema `chapter_plan.py` + prompt). *Decided:*
2026-06-04 (user choice "Ship 1-topic-per-chapter now; real topics as fast-follow").

**D-4: Vendor the Schema breakdown prompt into the Dars repo; do not read a workstation
path or import Schema as a module.** *Rationale:* the script reads
`/home/hataf/taleemabad/Schema/prompts/english_prompt.txt` at runtime — that path does
not exist on the Railway container, so the in-app service cannot depend on it. Schema is
not importable either (it pulls in `openai` + heavy deps; the script already re-implements
its parsing inline). *Apply:* copy the breakdown prompt text into the Dars repo under
`server/src/dars/v2_api/prompts/` (e.g. `slo_breakdown_english.txt`) and read it from the
package; port the inlined markdown-parse + lp_type classifier logic into the service.
Per-subject prompts: ship English now; other subjects either reuse the English prompt or
add their own prompt file (logged limitation — non-English books may break breakdown).
*Decided:* 2026-06-04.

**D-5: The import is admin-gated and runs inside the Dars app process.** *Rationale:* it's
a dashboard action; the app already has core-DB config plumbing
(`settings.effective_core_db_url`) and a session-based admin auth dep. *Apply:* both
endpoints depend on `get_current_admin` (from `admin_auth.py`, `X-Admin-Session` header,
returns `AdminContext`) — the **same dep the rest of the admin dashboard uses**
(router_admin.py, router_admin_tenancy.py); NOT the `X-Admin-Token` `require_admin` in
deps.py. Use `AdminContext` for `import_runs.started_by`. The import service opens its own short-lived asyncpg
connections — a read-only one to core (`effective_core_db_url`, `SET search_path TO
fde_staging, public`) and a read-write one to Dars — rather than reusing the request's
pooled connection (the background task outlives the request). The Dars writes run in a
single transaction that rolls back on any error (matches the script). *Decided:* 2026-06-04.

**D-6: Deterministic UUIDs keep imports idempotent.** *Rationale:* re-importing a book
(or re-running after a failure) must not duplicate rows. *Apply:* reuse the script's
`seed_uuid` scheme — `book:<CURR>:<GRADE>:<SUBJ>:<core_id>`, `slo:…`, `sub_slo:…`,
`topic:…`, `book_chapter:…` — derived from the same `SEED_NAMESPACE`. Generalised from
the script's hard-coded `NCP:G1:Eng` to use the resolved cell codes. All writes are
upserts (`ON CONFLICT … DO UPDATE`). `already_imported` in the browse list is computed by
checking whether the book's deterministic UUID exists in Dars `books`. *Decided:* 2026-06-04.

**D-7: Core DB access is required on the server; if unconfigured, the endpoints fail
cleanly.** *Rationale:* core-DB env vars may be absent on a given environment. *Apply:* if
`settings.effective_core_db_url` is empty, `GET /admin/core-books` and `POST
/admin/book-imports` return `503` with a clear message ("taleemabad-core DB not configured
on this server"). Setting the env vars on Railway is an ops step, flagged in the ONRAMP
(no secrets in git). *Decided:* 2026-06-04.

**D-10: The import UI lives at `/dashboard/admin/books`, not `/dashboard/curriculum/import`.**
*Rationale:* the dashboard sidebar (`components/molecules/dashboard/sidebar.tsx`) already has
an Admin → **Books** nav entry pointing at `/dashboard/admin/books` — a placeholder route that
didn't exist yet. Building the import page there fills the existing nav slot instead of
creating an orphan link + a parallel location. Supersedes the `05-phase-2-frontend.md` route
choice (`/dashboard/curriculum/import`). *Apply:* page at
`webapp/app/dashboard/admin/books/page.tsx`. *Decided:* 2026-06-04 (found the nav entry during
Phase 2).

**D-9: Sub-SLO code parser is ported verbatim and may not match the prompt's output
format — logged, not fixed, in Phase 1.** *Rationale:* the script's
`_SUB_SLO_CODE_RE = ^([A-Z]\d*-\d+)-[a-z]$` expects `A1-02-a`-style sub-SLO codes, but the
vendored breakdown prompt (rule 6) instructs the model to emit dot-notation
(`MainSLOCode.1`, e.g. `A-01.1`). These don't match, so the parser can silently drop sub-SLO
rows. The proven NCP run apparently produced compatible codes (the seed has 71 sub-SLOs), so
the script "worked" for that book — but a general import may not. *Apply:* Phase 1 ports the
parser as-is (faithful to the reference, D-3 spirit) and the service logs a warning ("0 usable
sub-SLOs … code format may not match the parser") instead of failing the run. **Follow-up
`core-book-import-subslo-code-format`:** reconcile the prompt's output format with the parser
(either loosen the regex to accept dot-notation, or change the prompt's rule 6, or have the
breakdown emit explicit parent+child columns). *Decided:* 2026-06-04 (discovered during F-1.4).

> **RESOLVED 2026-06-04 (D-11).** Replaced the single rigid regex with
> `_derive_parent_code(code, known_parents)`: it (1) keeps a bare code that exactly equals a
> known parent (unsplittable SLO), (2) strips any recognised suffix — `.N` dot-notation,
> `-a`/`-aa` hyphen-letter, `(N)` paren — then verifies the stripped parent is known, and
> (3) falls back to the longest known parent that prefixes the code. Validation is against the
> actual set of parent SLO codes, so it is format-agnostic. Positioning now uses
> `_sub_code_sort_key` (numeric-aware: `.2` before `.10`). Unit-tested in
> `test_book_import_service.py`. The "0 usable sub-SLOs" warning now only fires when rows
> genuinely map to no known parent, not on a format mismatch.

**D-8: Concurrency — one running import at a time (per server).** *Rationale:* the import
holds a Dars transaction and makes serial LLM calls; concurrent imports of the same book
would contend on the same deterministic UUIDs. *Apply:* `POST /admin/book-imports` rejects
with `409` if an `import_runs` row is already `running`. Simple guard for v1; revisit if
parallel imports of different cells are ever needed. *Decided:* 2026-06-04.

**D-11: Sub-SLO parent-code derivation is format-agnostic and validates against the known
parent set (resolves D-9).** *Rationale:* the ported regex matched only `A1-02-a`, but the
breakdown prompt emits dot-notation (`A-01.1`) or bare parent codes; a fresh import would drop
all/most sub-SLOs. *Apply:* `_derive_parent_code(code, known_parents)` (exact-parent →
strip-recognised-suffix → longest-known-prefix), plus `_sub_code_sort_key` for numeric-aware
ordering. Tested in `test_book_import_service.py`. *Decided:* 2026-06-04. *Resolves:* D-9.
