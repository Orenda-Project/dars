"""Import books and chapters from taleemabad-core into Dars."""
import logging
import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from dars.config import settings

log = logging.getLogger("curriculum.import_service")

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


async def import_books(db: AsyncSession, schema_filter: str | None = None) -> dict:
    """
    Import books+chapters from core DB into Dars.
    schema_filter: "fde_staging" | "balochistan_staging" | None (both)
    Returns {"imported": int, "skipped": int, "missing": int, "chapters": int}
    """
    if not settings.core_db_url:
        raise ValueError("CORE_DB_URL is not configured")

    books_to_import = BOOKS
    if schema_filter == "fde_staging":
        books_to_import = [(cid, cur, g, s) for (cid, cur, g, s) in BOOKS if SCHEMA[cur] == "fde_staging"]
    elif schema_filter == "balochistan_staging":
        books_to_import = [(cid, cur, g, s) for (cid, cur, g, s) in BOOKS if SCHEMA[cur] == "balochistan_staging"]

    core_conn = await asyncpg.connect(settings.core_db_url)
    imported = skipped = missing = chapters_total = 0

    try:
        for (core_id, curriculum, grade, subject) in books_to_import:
            schema = SCHEMA[curriculum]

            book_row = await core_conn.fetchrow(
                f"""
                SELECT id, title, publisher, edition, published_year, total_chapters, pdf_url, series
                FROM {schema}.book_library_book WHERE id = $1
                """,
                core_id,
            )
            if book_row is None:
                log.warning("Missing core book id=%s curriculum=%s", core_id, curriculum)
                missing += 1
                continue

            chapter_rows = await core_conn.fetch(
                f"""
                SELECT id, title, chapter_number, start_page, end_page
                FROM {schema}.book_library_bookchapter
                WHERE book_id = $1 ORDER BY chapter_number ASC
                """,
                core_id,
            )

            # Upsert book
            result = await db.execute(
                text("""
                    INSERT INTO books (core_id, curriculum, grade, subject, title, publisher,
                                       edition, published_year, total_chapters, pdf_url, series)
                    VALUES (:core_id, :curriculum, :grade, :subject, :title, :publisher,
                            :edition, :published_year, :total_chapters, :pdf_url, :series)
                    ON CONFLICT (core_id, curriculum) DO UPDATE SET
                        title=EXCLUDED.title, publisher=EXCLUDED.publisher,
                        edition=EXCLUDED.edition, published_year=EXCLUDED.published_year,
                        total_chapters=EXCLUDED.total_chapters, pdf_url=EXCLUDED.pdf_url,
                        series=EXCLUDED.series, updated_at=NOW()
                    RETURNING id
                """),
                dict(core_id=core_id, curriculum=curriculum, grade=grade, subject=subject,
                     title=book_row["title"], publisher=book_row["publisher"],
                     edition=book_row["edition"], published_year=book_row["published_year"],
                     total_chapters=book_row["total_chapters"], pdf_url=book_row["pdf_url"],
                     series=book_row["series"]),
            )
            dars_book_id = result.scalar_one()

            # Upsert chapters
            for ch in chapter_rows:
                await db.execute(
                    text("""
                        INSERT INTO book_chapters (core_id, book_id, title, chapter_number, start_page, end_page)
                        VALUES (:core_id, :book_id, :title, :chapter_number, :start_page, :end_page)
                        ON CONFLICT (core_id) DO UPDATE SET
                            title=EXCLUDED.title, chapter_number=EXCLUDED.chapter_number,
                            start_page=EXCLUDED.start_page, end_page=EXCLUDED.end_page,
                            updated_at=NOW()
                    """),
                    dict(core_id=ch["id"], book_id=str(dars_book_id),
                         title=ch["title"], chapter_number=ch["chapter_number"],
                         start_page=ch["start_page"], end_page=ch["end_page"]),
                )
                chapters_total += 1

            await db.commit()
            imported += 1
            log.info("Imported [%s] G%s %s core_id=%s chapters=%s", curriculum, grade, subject, core_id, len(chapter_rows))

    finally:
        await core_conn.close()

    return {"imported": imported, "skipped": skipped, "missing": missing, "chapters": chapters_total}
