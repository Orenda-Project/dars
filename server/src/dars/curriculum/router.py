import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.curriculum.admin_service import breakdown_chapter
from dars.curriculum.models import Book, BookChapter, LessonSlot, Topic
from dars.curriculum.schemas import (
    BookChapterListResponse,
    BookChapterResponse,
    BookListResponse,
    BookResponse,
    BreakdownResponse,
    LessonSlotListResponse,
    LessonSlotResponse,
    TopicListResponse,
    TopicResponse,
)
from dars.curriculum.service import list_book_chapters, list_books
from dars.database import get_db
from dars.deps import get_current_client, require_admin_secret

router = APIRouter(tags=["books"])
admin_router = APIRouter(prefix="/admin", tags=["admin-curriculum"])


# ---------------------------------------------------------------------------
# Client endpoints
# ---------------------------------------------------------------------------


@router.get("/api/v1/books", response_model=BookListResponse)
async def list_books_endpoint(
    curriculum: str | None = Query(default=None),
    grade: int | None = Query(default=None),
    subject: str | None = Query(default=None),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> BookListResponse:
    items, total = await list_books(db, curriculum=curriculum, grade=grade, subject=subject)
    return BookListResponse(
        items=[BookResponse.model_validate(b) for b in items],
        total=total,
    )


@router.get("/api/v1/books/{book_id}/chapters", response_model=BookChapterListResponse)
async def list_book_chapters_endpoint(
    book_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> BookChapterListResponse:
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    chapters = await list_book_chapters(db, book_id=book_id)
    return BookChapterListResponse(
        items=[BookChapterResponse.model_validate(c) for c in chapters],
    )


@router.get(
    "/api/v1/books/{book_id}/chapters/{chapter_id}/topics",
    response_model=TopicListResponse,
)
async def list_chapter_topics(
    book_id: uuid.UUID,
    chapter_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> TopicListResponse:
    # Verify chapter belongs to book
    chapter = await db.get(BookChapter, chapter_id)
    if chapter is None or chapter.book_id != book_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

    count_result = await db.execute(
        select(func.count()).where(Topic.chapter_id == chapter_id)
    )
    total = count_result.scalar_one()

    items_result = await db.execute(
        select(Topic)
        .where(Topic.chapter_id == chapter_id)
        .order_by(Topic.topic_number)
    )
    items = list(items_result.scalars().all())

    return TopicListResponse(
        items=[TopicResponse.model_validate(t) for t in items],
        total=total,
    )


@router.get("/api/v1/topics/{topic_id}/slots", response_model=LessonSlotListResponse)
async def list_topic_slots(
    topic_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> LessonSlotListResponse:
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    result = await db.execute(
        select(LessonSlot)
        .where(LessonSlot.topic_id == topic_id)
        .order_by(LessonSlot.day_number)
    )
    items = list(result.scalars().all())
    return LessonSlotListResponse(items=[LessonSlotResponse.model_validate(s) for s in items])


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@admin_router.post(
    "/chapters/{chapter_id}/breakdown",
    response_model=BreakdownResponse,
    dependencies=[Depends(require_admin_secret)],
)
async def breakdown_chapter_endpoint(
    chapter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BreakdownResponse:
    try:
        summary = await breakdown_chapter(db, chapter_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BreakdownResponse(**summary)
