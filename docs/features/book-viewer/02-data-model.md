# Data model — Book Viewer

**No schema change.** This feature is read-only. It reshapes existing tables into a
nested response. This doc records (a) the columns the tree reads and (b) the new
response shape returned by `GET /api/v2/books/{book_id}/tree`.

## Tables read (existing — ground truth is `docs/plans/2026-05-15-dars-v2-rebuild/02-data-model.md`)

| Table | Columns used |
|---|---|
| `books` | `id, curriculum_id, grade_id, subject_id, title, publisher, edition, published_year, total_chapters, pdf_url, book_text, created_at, updated_at` |
| `book_chapters` | `id, book_id, chapter_number, title, start_page, end_page, chapter_text, status, created_at, updated_at` |
| `book_chapter_slos` (join) | `book_chapter_id, slo_id` |
| `slos` | `id, code, statement, position` |
| `topics` | `id, book_chapter_id, topic_number, title, start_line, end_line, topic_text, status, created_at, updated_at` |
| `topic_sub_slos` (join) | `topic_id, sub_slo_id` |
| `sub_slos` | `id, code, statement, position` |

`book_text` and `chapter_text` are JSONB shaped `[{pdf_page_no, text}, ...]`
(asyncpg returns JSONB as a string — parse with the existing `_parse_jsonb` helper).

## New response shape — `BookTreeRead`

Returned by `GET /api/v2/books/{book_id}/tree`. One nested object; OCR always included
(D-3). Field shapes mirror the existing `BookRead` / `BookChapterRead` / `TopicRead`
plus the mini SLO shapes, so the frontend types compose from what's already in
`dars-api.ts`.

```jsonc
{
  // all BookRead fields, with book_text populated:
  "id": "...", "curriculum_id": "...", "grade_id": "...", "subject_id": "...",
  "title": "...", "publisher": "...", "edition": "...", "published_year": 2021,
  "total_chapters": 10, "pdf_url": "...",
  "book_text": [{ "pdf_page_no": 1, "text": "..." }],
  "created_at": "...", "updated_at": "...",
  "chapters": [
    {
      // all BookChapterRead fields, with chapter_text populated:
      "id": "...", "book_id": "...", "chapter_number": 1, "title": "...",
      "start_page": 1, "end_page": 8, "status": "...",
      "chapter_text": [{ "pdf_page_no": 1, "text": "..." }],
      "created_at": "...", "updated_at": "...",
      "slos": [{ "id": "...", "code": "...", "statement": "..." }],
      "topics": [
        {
          // all TopicRead fields:
          "id": "...", "book_chapter_id": "...", "topic_number": 1, "title": "...",
          "start_line": 0, "end_line": 12, "topic_text": "...", "status": "...",
          "created_at": "...", "updated_at": "...",
          "sub_slos": [{ "id": "...", "code": "...", "statement": "..." }]
        }
      ]
    }
  ]
}
```

### Pydantic schemas (in `schemas_book.py`)

- `BookChapterTreeRead(BookChapterRead)` — adds `slos: list[SLOMiniRead]` and
  `topics: list[TopicTreeRead]`.
- `TopicTreeRead(TopicRead)` — adds `sub_slos: list[SubSLOMiniRead]`.
- `BookTreeRead(BookRead)` — adds `chapters: list[BookChapterTreeRead]`.

Reuse the existing `SLOMiniRead` / `SubSLOMiniRead`. `book_text` / `chapter_text`
already exist (nullable) on `BookRead` / `BookChapterRead`; the tree just populates them.

### Query plan (assembly, ordered)

1. `books` row by `id` (404 if missing).
2. all `book_chapters` for the book, ordered by `chapter_number`.
3. all `topics` for those chapters in one `WHERE book_chapter_id = ANY($1)`, ordered by
   `(book_chapter_id, topic_number)`.
4. chapter→SLO join in one query: `book_chapter_slos JOIN slos`, `WHERE book_chapter_id
   = ANY($1)`, ordered by `(book_chapter_id, slos.position, slos.code)`.
5. topic→sub-SLO join in one query: `topic_sub_slos JOIN sub_slos`, `WHERE topic_id =
   ANY($1)`, ordered by `(topic_id, sub_slos.position, sub_slos.code)`.

Stitch in Python: group topics by `book_chapter_id`, SLOs by `book_chapter_id`, sub-SLOs
by `topic_id`. Total queries: 5, independent of chapter/topic count (no N+1).
