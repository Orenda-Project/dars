import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.config import settings
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
from dars.lesson_plans.models import LessonPlan
from dars.lesson_plans.schemas import LessonPlanResponse
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


@router.post(
    "/api/v1/slots/{slot_id}/generate-lp",
    response_model=LessonPlanResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_slot_lp(
    slot_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    """Generate (or regenerate) a lesson plan for a slot using its topic_text."""
    row = await db.execute(
        text("""
            SELECT
                ls.id, ls.lesson_plan_id,
                t.topic_text,
                ls.topic_subtopic AS topic,
                t.page_number,
                b.grade, b.subject, b.curriculum
            FROM lesson_slots ls
            JOIN topics t ON t.id = ls.topic_id
            JOIN book_chapters bc ON bc.id = t.chapter_id
            JOIN books b ON b.id = bc.book_id
            WHERE ls.id = :slot_id
        """),
        {"slot_id": str(slot_id)},
    )
    data = row.mappings().one_or_none()
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
    if not data["topic_text"]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Slot has no topic_text — run chapter breakdown first")

    lp = LessonPlan(
        client_id=current_client.id,
        curriculum=data["curriculum"],
        grade=str(data["grade"]),
        subject=data["subject"],
        topic=data["topic"],
        page_number=data["page_number"],
        status="PENDING",
    )
    db.add(lp)
    await db.flush()

    await db.execute(
        text("UPDATE lesson_slots SET lesson_plan_id = :lp_id WHERE id = :slot_id"),
        {"lp_id": str(lp.id), "slot_id": str(slot_id)},
    )
    await db.commit()
    await db.refresh(lp)

    slot_data = dict(data)
    lp_id = lp.id
    client_id = current_client.id

    async def _generate() -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from dars.mapping import canonical_grade, canonical_subject
        engine = create_async_engine(settings.database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        curriculum = slot_data["curriculum"]
        subject = canonical_subject(slot_data["subject"])
        grade = canonical_grade(slot_data["grade"])

        payload = {
            "grade": grade,
            "curriculum": curriculum,
            "subject": subject,
            "topic": slot_data["topic"],
            "page_content": slot_data["topic_text"] or "",
        }

        async with factory() as session:
            record = await session.get(LessonPlan, lp_id)
            if record is None:
                await engine.dispose()
                return
            try:
                async with httpx.AsyncClient(timeout=120.0) as http:
                    resp = await http.post(
                        f"{settings.lp_assistant_url}/api/generate-lp",
                        json=payload,
                        headers={"api-key": settings.lp_assistant_api_key},
                    )
                resp.raise_for_status()
                result = resp.json()
                record.content = result.get("lesson_plan", "")
                record.content_bilingual = result.get("lesson_plan_bilingual")
                record.tags = result.get("tags") or {}
                record.metadata_ = result.get("metadata") or {}
                record.status = "READY"
            except Exception as exc:
                import logging
                logging.getLogger(__name__).error("Slot LP generation failed lp=%s: %s", lp_id, exc)
                record.status = "ERROR"
            await session.commit()
        await engine.dispose()

    background_tasks.add_task(_generate)
    return LessonPlanResponse.model_validate(lp)


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


@router.post(
    "/api/v1/chapters/{chapter_id}/breakdown",
    response_model=BreakdownResponse,
    dependencies=[Depends(require_admin_secret)],
)
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
