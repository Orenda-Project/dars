# Phase 2 — Frontend (admin dashboard)

Bead `feat-core-book-import-phase-2`. Branch from `staging`. PRs → `staging`. Depends on
Phase 1 endpoints being live on staging. References: decision log, Phase 1 specs.

New dashboard area under `/dashboard/curriculum` (the import produces curriculum content,
so it lives beside the curriculum browser). Reuses Dars tokens / existing page idioms.

---

## F-2.1 — API client methods

**Spec.** In `webapp/lib/dars-api.ts` add an `admin`/`books` section:
`getCoreBooks(search?)`, `startBookImport({core_book_id, curriculum_id?})`,
`getImportRun(id)`, `getImportRuns()`, with types `CoreBook`, `ImportRun`
(status union, `steps`, `counts`, `warnings`, `error`, `dars_book_id`). All hit the
`/api/v2/admin/*` paths with the admin session.

**Acceptance.** `tsc --noEmit` + `eslint` clean. Types match the Phase 1 responses.

**Dependencies.** Phase 1 shipped.

---

## F-2.2 — Import page: book picker + start

**Spec.** New route `webapp/app/dashboard/curriculum/import/page.tsx`. Lists Core Books
from `getCoreBooks` with a search box; each row shows title, grade, subject, publisher,
chapter count, and an "Already imported" badge when flagged. Selecting a row reveals a
confirm panel: derived grade/subject (read-only, from the core row), a curriculum picker
(default active), and an **Import** button calling `startBookImport`. On 202, navigate to
/ show the progress view (F-2.3) for the returned run. Handle 409 ("an import is already
running"), 503 ("core not configured on this server"). Link to this page from the
curriculum browser.

**Acceptance.** Books list + search work against staging; selecting shows derived scope;
Import kicks off and transitions to progress. 409/503 surfaced as readable messages.

**Dependencies.** F-2.1.

---

## F-2.3 — Progress poller + results card

**Spec.** A component that polls `getImportRun(id)` (e.g. every 2s) while
`status ∈ {pending, running}`, rendering a per-step checklist (`slos`, `sub_slos`,
`book_chapters`, `topics`, `mappings`) with the current step highlighted and counts as
they land. On `succeeded`: a results card (row counts, any warnings, a link to the
imported book via the book-viewer `/dashboard/curriculum/books/{dars_book_id}`). On
`failed`: the error message + which step failed. Stop polling on a terminal status.

**Acceptance.** Live progress advances through steps against a real staging import; final
card shows counts + book link on success, error + step on failure; polling stops at a
terminal state (no infinite requests).

**Dependencies.** F-2.1 (and F-2.2 for entry).

---

## F-2.4 — Import history (optional, small)

**Spec.** On the import page, a collapsible "Recent imports" list from `getImportRuns()`
— book, cell, status, when, counts. Lets the admin revisit a past run / re-open its results.

**Acceptance.** Shows recent runs; clicking one opens its results/progress view.

**Dependencies.** F-2.1.

## Notes from execution
*(append-only)*
