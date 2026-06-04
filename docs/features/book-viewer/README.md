# Book Viewer — admin dashboard

Lets an admin view a book on the dashboard in two complementary ways on the same
page: a **Rendered** view (book metadata card → expandable chapters → topics, with
the OCR text per chapter and the linked SLOs / sub-SLOs) and a **Raw JSON** view —
a single collapsible block, **default collapsed (off)**, that dumps the entire book
as one nested object (book + chapters + topics + chapter→SLOs + topic→sub-SLOs, OCR
text included). Both views derive from the same single fetch, so they never disagree.

The book detail page already exists at `/dashboard/curriculum/books/[book_id]` and
renders chapters/topics. This feature (a) adds a backend "full book tree" assembly
endpoint so the whole tree comes back in one request, (b) enriches the rendered view
with book metadata, per-chapter OCR text, and linked SLOs/sub-SLOs, and (c) adds the
collapsible raw-JSON block.

## Documents

1. [01-decision-log.md](01-decision-log.md) — decisions `D-1`…, rationale + when decided.
2. [02-data-model.md](02-data-model.md) — no schema change; documents the existing
   tables/columns the tree reads and the new response shape.
3. [03-phase-1-book-viewer.md](03-phase-1-book-viewer.md) — the single phase: backend
   tree endpoint + frontend rendered enrichment + raw-JSON block.
4. [ONRAMP.md](ONRAMP.md) — *(written after plan approval)* single entry point for a
   fresh agent picking this up cold.

## Document precedence

```
1. 01-decision-log.md         (D-N references are canonical)
2. 02-data-model.md           (schema / response shape is ground truth)
3. phase docs                 (specs derived from above)
4. running code               (last; code may be stale)
```

If two docs disagree, this is the order. Code is lowest authority. Surface conflicts;
don't silently pick a side.
