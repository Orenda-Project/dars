"""
Import books and chapters from taleemabad-core into Dars.

Sources:
  ICT    → fde_staging.book_library_book / book_library_bookchapter
  Punjab → balochistan_staging.book_library_book / book_library_bookchapter

Books imported: English, Maths, Urdu — grades 1–5 for both curriculums.
These are the same book IDs used by UG_LessonPlan.

Usage:
    uv run python scripts/import_books.py \
        --dars-db   postgresql://user:pass@host:5432/dars \
        --core-db   postgresql://user:pass@host:5432/taleemabad

    # Dry run (read from core, print what would be upserted — no writes):
    uv run python scripts/import_books.py --core-db ... --dry-run
"""

import argparse
import json
import sys
import psycopg2
import psycopg2.extras
from psycopg2.extras import Json

# ── Book IDs (from UG_LessonPlan/config.py — single source of truth) ─────────

BOOKS = [
    # (core_book_id, curriculum, grade, subject)
    # ICT — fde_staging
    (1171, "ICT", 1, "Eng"),
    (1172, "ICT", 2, "Eng"),
    (1173, "ICT", 3, "Eng"),
    (1163, "ICT", 4, "Eng"),
    (1168, "ICT", 5, "Eng"),
    (1159, "ICT", 1, "Maths"),
    (1165, "ICT", 2, "Maths"),
    (1161, "ICT", 3, "Maths"),
    (1164, "ICT", 4, "Maths"),
    (1167, "ICT", 5, "Maths"),
    (1169, "ICT", 1, "Urdu"),
    (1175, "ICT", 2, "Urdu"),
    (1160, "ICT", 3, "Urdu"),
    (1170, "ICT", 4, "Urdu"),
    (1174, "ICT", 5, "Urdu"),
    # Punjab — balochistan_staging
    (1178, "Punjab", 1, "Eng"),
    (1179, "Punjab", 2, "Eng"),
    (1177, "Punjab", 3, "Eng"),
    (1180, "Punjab", 4, "Eng"),
    (1181, "Punjab", 5, "Eng"),
    (1196, "Punjab", 1, "Maths"),
    (1197, "Punjab", 2, "Maths"),
    (1191, "Punjab", 3, "Maths"),
    (1194, "Punjab", 4, "Maths"),
    (1195, "Punjab", 5, "Maths"),
    (1189, "Punjab", 1, "Urdu"),
    (1188, "Punjab", 2, "Urdu"),
    (1187, "Punjab", 3, "Urdu"),
    (1184, "Punjab", 4, "Urdu"),
    (1183, "Punjab", 5, "Urdu"),
]

SCHEMA = {
    "ICT": "fde_staging",
    "Punjab": "balochistan_staging",
}


def fetch_book(core_cur, schema: str, book_id: int) -> dict | None:
    core_cur.execute(
        f"""
        SELECT id, title, publisher, edition, published_year, total_chapters, pdf_url, series, book_text
        FROM {schema}.book_library_book
        WHERE id = %s
        """,
        (book_id,),
    )
    row = core_cur.fetchone()
    if row is None:
        return None
    return {
        "core_id": row["id"],
        "title": row["title"],
        "publisher": row["publisher"],
        "edition": row["edition"],
        "published_year": row["published_year"],
        "total_chapters": row["total_chapters"],
        "pdf_url": row["pdf_url"],
        "series": row["series"],
        "book_text": Json(row["book_text"]) if row["book_text"] is not None else None,
    }


def fetch_chapters(core_cur, schema: str, book_id: int) -> list[dict]:
    core_cur.execute(
        f"""
        SELECT id, title, chapter_number, start_page, end_page
        FROM {schema}.book_library_bookchapter
        WHERE book_id = %s
        ORDER BY chapter_number ASC
        """,
        (book_id,),
    )
    return [
        {
            "core_id": row["id"],
            "title": row["title"],
            "chapter_number": row["chapter_number"],
            "start_page": row["start_page"],
            "end_page": row["end_page"],
        }
        for row in core_cur.fetchall()
    ]


def upsert_book(dars_cur, book: dict, curriculum: str, grade: int, subject: str) -> int:
    """Upsert into dars.books, return the dars book id."""
    dars_cur.execute(
        """
        INSERT INTO books (core_id, curriculum, grade, subject, title, publisher, edition,
                           published_year, total_chapters, pdf_url, series, book_text)
        VALUES (%(core_id)s, %(curriculum)s, %(grade)s, %(subject)s, %(title)s,
                %(publisher)s, %(edition)s, %(published_year)s, %(total_chapters)s,
                %(pdf_url)s, %(series)s, %(book_text)s)
        ON CONFLICT (core_id, curriculum) DO UPDATE SET
            title          = EXCLUDED.title,
            publisher      = EXCLUDED.publisher,
            edition        = EXCLUDED.edition,
            published_year = EXCLUDED.published_year,
            total_chapters = EXCLUDED.total_chapters,
            pdf_url        = EXCLUDED.pdf_url,
            series         = EXCLUDED.series,
            book_text      = EXCLUDED.book_text,
            updated_at     = NOW()
        RETURNING id
        """,
        {**book, "curriculum": curriculum, "grade": grade, "subject": subject},
    )
    return dars_cur.fetchone()["id"]


def upsert_chapters(dars_cur, chapters: list[dict], dars_book_id: int) -> int:
    count = 0
    for ch in chapters:
        dars_cur.execute(
            """
            INSERT INTO book_chapters (core_id, book_id, title, chapter_number, start_page, end_page)
            VALUES (%(core_id)s, %(book_id)s, %(title)s, %(chapter_number)s, %(start_page)s, %(end_page)s)
            ON CONFLICT (core_id) DO UPDATE SET
                title          = EXCLUDED.title,
                chapter_number = EXCLUDED.chapter_number,
                start_page     = EXCLUDED.start_page,
                end_page       = EXCLUDED.end_page,
                updated_at     = NOW()
            """,
            {**ch, "book_id": dars_book_id},
        )
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description="Import books from taleemabad-core into Dars")
    parser.add_argument("--core-db", required=True, help="Core DB connection string")
    parser.add_argument("--dars-db", help="Dars DB connection string (omit for --dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print, no writes")
    args = parser.parse_args()

    if not args.dry_run and not args.dars_db:
        print("ERROR: --dars-db is required unless --dry-run is set", file=sys.stderr)
        sys.exit(1)

    core_conn = psycopg2.connect(args.core_db, cursor_factory=psycopg2.extras.RealDictCursor)
    core_cur = core_conn.cursor()

    dars_conn = dars_cur = None
    if not args.dry_run:
        dars_conn = psycopg2.connect(args.dars_db, cursor_factory=psycopg2.extras.RealDictCursor)
        dars_cur = dars_conn.cursor()

    books_ok = books_missing = chapters_total = 0

    for (core_id, curriculum, grade, subject) in BOOKS:
        schema = SCHEMA[curriculum]
        book = fetch_book(core_cur, schema, core_id)

        if book is None:
            print(f"  MISSING  [{curriculum}] grade={grade} {subject} core_id={core_id}")
            books_missing += 1
            continue

        chapters = fetch_chapters(core_cur, schema, core_id)

        if args.dry_run:
            has_text = "book_text=YES" if book["book_text"] else "book_text=NO"
            print(
                f"  OK  [{curriculum}] grade={grade} {subject:6s} core_id={core_id:5d}"
                f"  title='{book['title']}'  chapters={len(chapters)}  {has_text}"
            )
        else:
            dars_book_id = upsert_book(dars_cur, book, curriculum, grade, subject)
            n = upsert_chapters(dars_cur, chapters, dars_book_id)
            print(
                f"  UPSERTED [{curriculum}] grade={grade} {subject:6s} core_id={core_id:5d}"
                f"  dars_id={dars_book_id}  chapters={n}"
            )
            chapters_total += n

        books_ok += 1

    if not args.dry_run:
        dars_conn.commit()
        dars_cur.close()
        dars_conn.close()

    core_cur.close()
    core_conn.close()

    print(f"\nDone. books={books_ok} missing={books_missing} chapters={chapters_total}")


if __name__ == "__main__":
    main()
