import re
from datetime import datetime, timezone

import psycopg2
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from dars.config import settings
from dars.books.models import Book, BookChapter


BOOKS_QUERY = """
SELECT b.id, b.title, b.cover_image, b.total_chapters,
       g.label as grade, s.short_code as subject, b.book_text
FROM {schema}.book_library_book b
JOIN {schema}.slo_gradesubject gs ON gs.id = b.grade_subject_id
JOIN {schema}.slo_grade g ON g.id = gs.grade_id
JOIN {schema}.slo_subject s ON s.id = gs.subject_id
WHERE b.is_active = true
"""

CHAPTERS_QUERY = """
SELECT id, title, chapter_number, start_page, end_page, book_id
FROM {schema}.book_library_bookchapter
WHERE book_id = ANY(%s) AND is_active = true
"""


def _get_core_conn():
    return psycopg2.connect(
        host=settings.core_db_host,
        port=settings.core_db_port,
        database=settings.core_db_name,
        user=settings.core_db_user,
        password=settings.core_db_password,
        connect_timeout=10,
    )


def _extract_grade_int(label: str) -> int:
    """Extract integer from grade labels like 'Grade 1', '1', 'Grade 10'."""
    match = re.search(r"\d+", str(label))
    return int(match.group()) if match else 0


def _fetch_books_from_schema(cur, schema: str, curriculum: str) -> list[dict]:
    cur.execute(BOOKS_QUERY.format(schema=schema))
    rows = cur.fetchall()
    books = []
    for row in rows:
        book_id, title, cover_image, total_chapters, grade_label, subject, book_text = row
        books.append({
            "id": book_id,
            "title": title,
            "cover_image": cover_image,
            "total_chapters": total_chapters,
            "grade": _extract_grade_int(grade_label),
            "subject": subject,
            "curriculum": curriculum,
            "book_text": book_text,
        })
    return books


def _fetch_chapters_from_schema(cur, schema: str, book_ids: list[int]) -> list[dict]:
    if not book_ids:
        return []
    cur.execute(CHAPTERS_QUERY.format(schema=schema), (book_ids,))
    rows = cur.fetchall()
    return [
        {
            "id": row[0],
            "title": row[1],
            "chapter_number": row[2],
            "start_page": row[3],
            "end_page": row[4],
            "book_id": row[5],
        }
        for row in rows
    ]


async def sync_books(db: AsyncSession) -> dict:
    """Sync books and chapters from taleemabad-core into local tables."""
    now = datetime.now(timezone.utc)

    conn = _get_core_conn()
    try:
        cur = conn.cursor()

        ict_books = _fetch_books_from_schema(cur, "fde_staging", "ICT")
        punjab_books = _fetch_books_from_schema(cur, "balochistan_staging", "Punjab")

        all_books = ict_books + punjab_books

        ict_ids = [b["id"] for b in ict_books]
        punjab_ids = [b["id"] for b in punjab_books]

        ict_chapters = _fetch_chapters_from_schema(cur, "fde_staging", ict_ids)
        punjab_chapters = _fetch_chapters_from_schema(cur, "balochistan_staging", punjab_ids)

        all_chapters = ict_chapters + punjab_chapters

        cur.close()
    finally:
        conn.close()

    if all_books:
        for book in all_books:
            book["synced_at"] = now

        stmt = pg_insert(Book).values(all_books)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "title": stmt.excluded.title,
                "grade": stmt.excluded.grade,
                "subject": stmt.excluded.subject,
                "curriculum": stmt.excluded.curriculum,
                "cover_image": stmt.excluded.cover_image,
                "total_chapters": stmt.excluded.total_chapters,
                "book_text": stmt.excluded.book_text,
                "synced_at": stmt.excluded.synced_at,
            },
        )
        await db.execute(stmt)

    if all_chapters:
        stmt = pg_insert(BookChapter).values(all_chapters)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "book_id": stmt.excluded.book_id,
                "title": stmt.excluded.title,
                "chapter_number": stmt.excluded.chapter_number,
                "start_page": stmt.excluded.start_page,
                "end_page": stmt.excluded.end_page,
            },
        )
        await db.execute(stmt)

    await db.commit()

    pages_synced = sum(1 for b in all_books if b.get("book_text") is not None)

    return {
        "ict_books": len(ict_books),
        "punjab_books": len(punjab_books),
        "chapters": len(all_chapters),
        "pages_synced": pages_synced,
    }


async def list_books(
    db: AsyncSession,
    curriculum: str | None = None,
    grade: int | None = None,
    subject: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Book], int]:
    query = select(Book)
    count_query = select(func.count()).select_from(Book)

    if curriculum:
        query = query.where(Book.curriculum == curriculum)
        count_query = count_query.where(Book.curriculum == curriculum)
    if grade is not None:
        query = query.where(Book.grade == grade)
        count_query = count_query.where(Book.grade == grade)
    if subject:
        query = query.where(Book.subject == subject)
        count_query = count_query.where(Book.subject == subject)

    query = query.order_by(Book.curriculum, Book.grade, Book.subject).limit(limit).offset(offset)

    result = await db.execute(query)
    total_result = await db.execute(count_query)

    return result.scalars().all(), total_result.scalar_one()
