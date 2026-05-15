"""
F1.8 — Read-only API for book / chapter / topic entities.

Public endpoints (no API key required) — books and curriculum content
are global per D-24.

book_text and chapter_text are excluded from responses by default
(can be large); include them with ?include=book_text / ?include=chapter_text.
topic_text is always included (small per topic).
"""
import json
import logging
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from dars.v2_api.deps import get_db_conn
from dars.v2_api.schemas_book import (
    BookChapterListResponse,
    BookChapterRead,
    BookListResponse,
    BookRead,
    ChapterSLOsResponse,
    SLOMiniRead,
    SubSLOMiniRead,
    TopicListResponse,
    TopicRead,
    TopicSubSLOsResponse,
)

log = logging.getLogger("v2_api.book")

router = APIRouter(prefix="/api/v2", tags=["v2-book"])


def _parse_jsonb(value):
    """asyncpg returns JSONB as str; parse to Python or pass through dict."""
    if value is None or isinstance(value, (list, dict)):
        return value
    return json.loads(value)


# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------

@router.get("/books", response_model=BookListResponse)
async def list_books(
    curriculum_id: UUID | None = Query(default=None),
    grade_id: UUID | None = Query(default=None),
    subject_id: UUID | None = Query(default=None),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BookListResponse:
    where = []
    params: list = []
    if curriculum_id is not None:
        params.append(curriculum_id)
        where.append(f"curriculum_id = ${len(params)}")
    if grade_id is not None:
        params.append(grade_id)
        where.append(f"grade_id = ${len(params)}")
    if subject_id is not None:
        params.append(subject_id)
        where.append(f"subject_id = ${len(params)}")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = await conn.fetch(
        f"""
        SELECT id, curriculum_id, grade_id, subject_id, title, publisher, edition,
               published_year, total_chapters, pdf_url, created_at, updated_at
        FROM books
        {where_sql}
        ORDER BY title
        """,
        *params,
    )
    return BookListResponse(items=[BookRead(**dict(r)) for r in rows])


@router.get("/books/{book_id}", response_model=BookRead)
async def get_book(
    book_id: UUID,
    include: str | None = Query(default=None, description="'book_text' to include OCR content"),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BookRead:
    include_text = include == "book_text"
    cols = (
        "id, curriculum_id, grade_id, subject_id, title, publisher, edition, "
        "published_year, total_chapters, pdf_url, created_at, updated_at"
    )
    if include_text:
        cols += ", book_text"
    row = await conn.fetchrow(
        f"SELECT {cols} FROM books WHERE id = $1",
        book_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    data = dict(row)
    if include_text:
        data["book_text"] = _parse_jsonb(data.get("book_text"))
    return BookRead(**data)


# ---------------------------------------------------------------------------
# Book chapters
# ---------------------------------------------------------------------------

@router.get("/book-chapters", response_model=BookChapterListResponse)
async def list_book_chapters(
    book_id: UUID = Query(..., description="Required; chapters are scoped to a book"),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BookChapterListResponse:
    rows = await conn.fetch(
        """
        SELECT id, book_id, chapter_number, title, start_page, end_page, status,
               created_at, updated_at
        FROM book_chapters
        WHERE book_id = $1
        ORDER BY chapter_number
        """,
        book_id,
    )
    return BookChapterListResponse(items=[BookChapterRead(**dict(r)) for r in rows])


@router.get("/book-chapters/{chapter_id}", response_model=BookChapterRead)
async def get_book_chapter(
    chapter_id: UUID,
    include: str | None = Query(default=None, description="'chapter_text' to include OCR content"),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BookChapterRead:
    include_text = include == "chapter_text"
    cols = (
        "id, book_id, chapter_number, title, start_page, end_page, status, "
        "created_at, updated_at"
    )
    if include_text:
        cols += ", chapter_text"
    row = await conn.fetchrow(
        f"SELECT {cols} FROM book_chapters WHERE id = $1",
        chapter_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    data = dict(row)
    if include_text:
        data["chapter_text"] = _parse_jsonb(data.get("chapter_text"))
    return BookChapterRead(**data)


@router.get("/book-chapters/{chapter_id}/slos", response_model=ChapterSLOsResponse)
async def get_book_chapter_slos(
    chapter_id: UUID,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> ChapterSLOsResponse:
    # Confirm chapter exists for a cleaner 404
    exists = await conn.fetchval("SELECT 1 FROM book_chapters WHERE id = $1", chapter_id)
    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    rows = await conn.fetch(
        """
        SELECT s.id, s.code, s.statement
        FROM book_chapter_slos bcs
        JOIN slos s ON s.id = bcs.slo_id
        WHERE bcs.book_chapter_id = $1
        ORDER BY s.position, s.code
        """,
        chapter_id,
    )
    return ChapterSLOsResponse(items=[SLOMiniRead(**dict(r)) for r in rows])


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

@router.get("/topics", response_model=TopicListResponse)
async def list_topics(
    book_chapter_id: UUID = Query(..., description="Required; topics are scoped to a chapter"),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> TopicListResponse:
    rows = await conn.fetch(
        """
        SELECT id, book_chapter_id, topic_number, title, start_line, end_line,
               topic_text, status, created_at, updated_at
        FROM topics
        WHERE book_chapter_id = $1
        ORDER BY topic_number
        """,
        book_chapter_id,
    )
    return TopicListResponse(items=[TopicRead(**dict(r)) for r in rows])


@router.get("/topics/{topic_id}", response_model=TopicRead)
async def get_topic(
    topic_id: UUID,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> TopicRead:
    row = await conn.fetchrow(
        """
        SELECT id, book_chapter_id, topic_number, title, start_line, end_line,
               topic_text, status, created_at, updated_at
        FROM topics WHERE id = $1
        """,
        topic_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return TopicRead(**dict(row))


@router.get("/topics/{topic_id}/sub-slos", response_model=TopicSubSLOsResponse)
async def get_topic_sub_slos(
    topic_id: UUID,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> TopicSubSLOsResponse:
    exists = await conn.fetchval("SELECT 1 FROM topics WHERE id = $1", topic_id)
    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    rows = await conn.fetch(
        """
        SELECT ss.id, ss.code, ss.statement
        FROM topic_sub_slos tss
        JOIN sub_slos ss ON ss.id = tss.sub_slo_id
        WHERE tss.topic_id = $1
        ORDER BY ss.position, ss.code
        """,
        topic_id,
    )
    return TopicSubSLOsResponse(items=[SubSLOMiniRead(**dict(r)) for r in rows])
