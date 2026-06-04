# Phase 1 — Book Viewer (rendered + raw JSON)

One phase, one bead (`feat-book-viewer-phase-1`), one PR target `staging`. Features are
numbered F-1.N and depend strictly on earlier ones. Each is small; F-1.1 is backend,
the rest are frontend on the same page.

References: [01-decision-log.md](01-decision-log.md) (D-1…D-6),
[02-data-model.md](02-data-model.md) (response shape + query plan).

---

## F-1.1 — Backend: `GET /api/v2/books/{book_id}/tree`

**Spec.** Add a full-tree assembly endpoint to `server/src/dars/v2_api/router_book.py`
(D-2). Public, no auth, only `get_db_conn` (D-4). Always includes OCR (D-3). Use the
5-query plan in `02-data-model.md` — bulk-fetch then stitch in Python, no N+1. Parse
`book_text` / `chapter_text` JSONB with the existing `_parse_jsonb` helper. 404 if the
book id doesn't exist.

Add the schemas to `server/src/dars/v2_api/schemas_book.py`:
`TopicTreeRead(TopicRead)` (+ `sub_slos`), `BookChapterTreeRead(BookChapterRead)`
(+ `slos`, `topics`), `BookTreeRead(BookRead)` (+ `chapters`). Reuse `SLOMiniRead` /
`SubSLOMiniRead`.

Structured logging per project rule 11: entry log with `book_id`, exit log with chapter
+ topic counts, errors at `ERROR` with `exc_info=True`.

**Acceptance.**
- `GET /api/v2/books/{seed_g1_english_book_id}/tree` returns 200 with `chapters[]`, each
  having `slos[]`, `chapter_text` (non-null for the seed), and `topics[]`, each topic
  having `sub_slos[]` and `topic_text`.
- `book_text` is present and non-null on the top object.
- `GET /api/v2/books/{random_uuid}/tree` returns 404.
- Query count does not grow with chapter/topic count (verify by reading the code: 5
  fixed queries).

**Dependencies.** None.

---

## F-1.2 — Frontend: types + `getBookTree()` client

**Spec.** In `webapp/lib/dars-api.ts`:
- Expand the truncated `Book` interface so the rendered card can show metadata. Add the
  fields the backend already returns: `publisher`, `edition`, `published_year`,
  `total_chapters`, `pdf_url`, `book_text` (typed `BookTextEntry[] | null` where
  `BookTextEntry = Record<string, unknown>`), `curriculum_id`/`grade_id`/`subject_id`
  already present. Keep existing consumers compiling (the new fields are optional-safe
  to read; do not remove `id`/`title`).
- Add tree types composing existing ones: `TopicTree extends Topic { sub_slos: SLOMini[] }`,
  `BookChapterTree extends BookChapter { slos: SLOMini[]; topics: TopicTree[] }`,
  `BookTree extends Book { chapters: BookChapterTree[] }`. Reuse the existing mini SLO
  type if one exists; otherwise add `SLOMini { id; code; statement }`.
- Add `books.getBookTree(id)` → `request<BookTree>(\`/api/v2/books/${id}/tree\`)`.

**Acceptance.** `npm run build` (or `tsc`) passes. `getBookTree` returns the typed tree.
No existing import of `Book` breaks.

**Dependencies.** F-1.1 (endpoint exists).

---

## F-1.3 — Frontend: rendered view enrichment

**Spec.** Rewrite `webapp/app/dashboard/curriculum/books/[book_id]/page.tsx` to fetch
once via `getBookTree(bookId)` (D-6) instead of the three separate calls. Keep the
existing visual language (Dars tokens, Cormorant heading, parchment cards, expandable
chapters). Enrich:
- **Book metadata card** at the top: title, publisher · edition · published_year,
  `total_chapters`, and a `pdf_url` link if present.
- **Per chapter** (expand as today): show `start_page–end_page`, `status`, the linked
  **SLOs** (`code` + `statement`), the chapter's **OCR text** (`chapter_text`) behind a
  small per-chapter "Show text" toggle (it can be long — keep it collapsed by default,
  consistent with the existing CPE per-unit "Show Text" pattern referenced in commit
  f3dccd9), then the **topics**.
- **Per topic**: `topic_number`, `title`, `topic_text`, and linked **sub-SLOs**
  (`code` + `statement`).

Because the tree is one payload, expanding a chapter is now pure client state (no
fetch) — drop the `loadTopics` fetch-on-expand logic; toggle from in-memory data.

**Acceptance.**
- Visiting the seed G1 English book shows the metadata card, chapters with SLOs, a
  per-chapter "Show text" revealing OCR, topics with topic_text, and sub-SLOs.
- Expanding/collapsing a chapter does not trigger a network request (data already loaded).
- Loading + error states preserved (existing `formatErr`).

**Dependencies.** F-1.2.

---

## F-1.4 — Frontend: collapsible raw JSON block

**Spec.** On the same page, below the rendered tree, add a **Raw JSON** collapsible
(D-5), **default collapsed**. When expanded it shows the entire `BookTree` object
pretty-printed (`JSON.stringify(tree, null, 2)`) in a scrollable monospace `<pre>` with
Dars tokens. Include a small "Copy" button that copies the JSON to the clipboard. Use a
native `<details>`/`<summary>` (no shadcn dependency needed) styled to match.

**Acceptance.**
- The block is collapsed on first load; the rendered view is what's visible.
- Expanding shows the full tree JSON including `book_text`, `chapter_text`, `slos`,
  `sub_slos`.
- Copy button puts valid JSON on the clipboard.
- No layout shift breaks the rendered view above it.

**Dependencies.** F-1.3 (shares the single fetched `tree`).

---

## Notes from execution

*(append-only; added during implementation if scope shifts or follow-ups emerge)*
