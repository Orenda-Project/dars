# Decision log — Book Viewer

Indexed `D-1`, `D-2`, … Decisions are frozen. To revise: ask the user, mark the old
one "Superseded by D-N on YYYY-MM-DD", add the new one referencing the supersession.

---

**D-1: Raw JSON view shows the full book tree with OCR included.** *Rationale:* the
admin wants to inspect exactly what the curriculum/generation pipeline sees, including
the OCR text the LP generator is fed. A lightweight (OCR-excluded) or per-entity dump
was offered; the user picked the full tree + OCR. *Apply:* the raw-JSON block dumps one
nested object: `book` (with `book_text`) → `chapters` (each with `chapter_text` + linked
`slos`) → `topics` (each with `topic_text` + linked `sub_slos`). *Decided:* 2026-06-04
(plan approval, user choice "Full book tree + OCR").

**D-2: Add one backend "full book tree" assembly endpoint rather than fan out N calls
from the browser.** *Rationale:* the existing API is one-entity-per-call (book, then
chapters, then per-chapter topics, then per-chapter SLOs, then per-topic sub-SLOs). For
a book with C chapters and T topics that is `1 + 1 + C + C + T` round trips — slow, and
the raw JSON would have to be re-stitched client-side and could drift from the rendered
view. A single `GET /api/v2/books/{book_id}/tree` assembles the whole nested object
server-side in a few bulk queries. Both views render off this one payload, so they can
never disagree (supports D-1). *Apply:* new endpoint in `router_book.py`; new
`BookTreeRead` schema in `schemas_book.py`; new `books.getBookTree()` in `dars-api.ts`.
*Decided:* 2026-06-04.

**D-3: The tree endpoint always includes OCR text (`book_text`, `chapter_text`).**
*Rationale:* D-1 says the raw view needs OCR; assembling the tree without it then
re-fetching with it would defeat the single-fetch design. The G1 English seed book is
the only real book and its OCR is bounded (10 chapters); payload size is acceptable.
*Apply:* the tree query selects `book_text` and `chapter_text` unconditionally; no
`?include=` flag on the tree endpoint. The existing per-entity `?include=` flags on
`GET /books/{id}` and `GET /book-chapters/{id}` are left untouched. *Decided:* 2026-06-04.

**D-4: Tree endpoint is public (no API key), matching the existing book endpoints.**
*Rationale:* `router_book.py` book/chapter/topic reads are already public per D-24 of the
v2 rebuild (curriculum content is global, not org-scoped). The tree is the same data
reshaped, so it carries the same access posture. The dashboard page that calls it is
admin-gated at the route level regardless. *Apply:* no `Depends` auth on the new
endpoint, only `get_db_conn`. *Decided:* 2026-06-04.

**D-5: Raw JSON block defaults collapsed (off); rendered view is the default visible
content.** *Rationale:* explicit user requirement ("raw JSON as a collapsable default
off"). The rendered view is the primary, human-readable surface; raw JSON is an
inspect-on-demand affordance. *Apply:* a `<details>` (or equivalent toggle) with no
`open` attribute, placed below the rendered tree (or in a clearly separate panel).
*Decided:* 2026-06-04.

**D-6: Reuse the existing book detail page; do not add a new route.** *Rationale:* the
page at `/dashboard/curriculum/books/[book_id]` already renders chapters/topics. This
feature enriches it (metadata + OCR + SLOs) and adds the JSON block, rather than
introducing a parallel route. *Apply:* edit `webapp/app/dashboard/curriculum/books/
[book_id]/page.tsx` in place; switch its data source from the three separate calls to
the single `getBookTree()` call. *Decided:* 2026-06-04.
