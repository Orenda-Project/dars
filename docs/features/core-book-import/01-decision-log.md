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
(`settings.effective_core_db_url`) and `require_admin`. *Apply:* both endpoints depend on
`require_admin` (from `deps.py`). The import service opens its own short-lived asyncpg
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

**D-8: Concurrency — one running import at a time (per server).** *Rationale:* the import
holds a Dars transaction and makes serial LLM calls; concurrent imports of the same book
would contend on the same deterministic UUIDs. *Apply:* `POST /admin/book-imports` rejects
with `409` if an `import_runs` row is already `running`. Simple guard for v1; revisit if
parallel imports of different cells are ever needed. *Decided:* 2026-06-04.
