import logging
import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.config import settings
from dars.curriculum.admin_service import breakdown_chapter
from dars.curriculum.import_service import import_books, import_single_book, list_known_books, preview_book
from dars.curriculum.models import Book, BookChapter, LessonSlot, Topic
from dars.curriculum.schemas import (
    BookChapterListResponse,
    BookChapterResponse,
    BookCurriculumResponse,
    BookListResponse,
    BookPreviewResponse,
    BookResponse,
    BreakdownResponse,
    ChapterPreview,
    CurriculumChapter,
    CurriculumLesson,
    CurriculumTopic,
    ImportBooksRequest,
    ImportBooksResponse,
    ImportSingleBookRequest,
    ImportSingleBookResponse,
    KnownBookEntry,
    KnownBooksResponse,
    LessonSlotListResponse,
    LessonSlotResponse,
    TopicListResponse,
    TopicResponse,
)
from dars.lesson_plans.models import LessonPlan
from dars.lesson_plans.schemas import LessonPlanResponse
from dars.curriculum.service import list_book_chapters, list_books
from dars.database import get_db
from dars.deps import get_admin_client, get_current_client, require_admin_secret

logger = logging.getLogger(__name__)

router = APIRouter(tags=["books"])


def _format_page_range(start: int | None, end: int | None) -> str | None:
    if start is None:
        return None
    if end is None or end == start:
        return str(start)
    return f"{start}-{end}"
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
    logger.info("list_books_endpoint: filters curriculum=%s grade=%s subject=%s", curriculum, grade, subject)
    items, total = await list_books(db, curriculum=curriculum, grade=grade, subject=subject)
    logger.info("list_books_endpoint: returning count=%d total=%d", len(items), total)
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
    logger.info("list_book_chapters_endpoint: book_id=%s", book_id)
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    chapters = await list_book_chapters(db, book_id=book_id)
    logger.info("list_book_chapters_endpoint: book_id=%s count=%d", book_id, len(chapters))
    return BookChapterListResponse(
        items=[BookChapterResponse.model_validate(c) for c in chapters],
    )


@router.get("/api/v1/books/{book_id}/stats")
async def get_book_stats(
    book_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> dict:
    logger.info("get_book_stats: book_id=%s", book_id)
    row = await db.execute(
        text("""
            SELECT
                COUNT(DISTINCT bc.id)                                          AS total_chapters,
                COUNT(DISTINCT CASE WHEN t.id IS NOT NULL THEN bc.id END)      AS chapters_broken_down,
                COUNT(DISTINCT ls.id)                                          AS total_slots,
                COUNT(DISTINCT ls.lesson_plan_id)                              AS lps_generated,
                COUNT(DISTINCT a.id)                                           AS quizzes_generated
            FROM book_chapters bc
            LEFT JOIN topics t        ON t.chapter_id = bc.id
            LEFT JOIN lesson_slots ls ON ls.topic_id = t.id
            LEFT JOIN assessments a   ON a.lesson_plan_id = ls.lesson_plan_id
            WHERE bc.book_id = :book_id
        """),
        {"book_id": str(book_id)},
    )
    data = dict(row.mappings().one())
    logger.info("get_book_stats: book_id=%s stats=%s", book_id, data)
    return data


@router.get("/api/v1/curriculum", response_model=BookCurriculumResponse)
async def get_book_curriculum(
    grade: int = Query(...),
    subject: str = Query(...),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> BookCurriculumResponse:
    """
    Full curriculum tree for the client's curriculum, filtered by grade and subject.
    Returns chapters → topics → lessons (with lesson_plan_id and assessment_id).
    Client's curriculum is read from their profile — they don't need to send it.
    """
    if not current_client.curriculum:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Client has no curriculum configured")

    logger.info("get_book_curriculum: client_id=%s curriculum=%s grade=%s subject=%s", current_client.id, current_client.curriculum, grade, subject)

    book_result = await db.execute(
        select(Book).where(
            Book.curriculum == current_client.curriculum,
            Book.grade == grade,
            Book.subject == subject,
        )
    )
    book = book_result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No book found for this grade and subject")

    rows = await db.execute(
        text("""
            SELECT
                bc.id           AS chapter_id,
                bc.chapter_number,
                bc.title        AS chapter_title,
                bc.start_page   AS chapter_start_page,
                bc.end_page     AS chapter_end_page,
                t.id            AS topic_id,
                t.topic_number,
                t.title         AS topic_title,
                t.start_page    AS topic_start_page,
                t.end_page      AS topic_end_page,
                ls.id           AS slot_id,
                ls.day_number,
                ls.topic_subtopic,
                ls.lesson_plan_id,
                a.id            AS assessment_id
            FROM book_chapters bc
            LEFT JOIN topics t        ON t.chapter_id = bc.id
            LEFT JOIN lesson_slots ls ON ls.topic_id = t.id
            LEFT JOIN assessments a   ON a.lesson_plan_id = ls.lesson_plan_id
            WHERE bc.book_id = :book_id
            ORDER BY bc.chapter_number, t.topic_number, ls.day_number
        """),
        {"book_id": str(book.id)},
    )
    all_rows = rows.mappings().all()

    chapters: dict[uuid.UUID, CurriculumChapter] = {}
    topics: dict[uuid.UUID, CurriculumTopic] = {}

    for r in all_rows:
        ch_id = uuid.UUID(str(r["chapter_id"]))
        if ch_id not in chapters:
            chapters[ch_id] = CurriculumChapter(
                id=ch_id,
                chapter_number=r["chapter_number"],
                title=r["chapter_title"],
                start_page=r["chapter_start_page"],
                end_page=r["chapter_end_page"],
                topics=[],
            )

        if r["topic_id"] is None:
            continue
        t_id = uuid.UUID(str(r["topic_id"]))
        if t_id not in topics:
            topic = CurriculumTopic(
                id=t_id,
                topic_number=r["topic_number"],
                title=r["topic_title"],
                start_page=r["topic_start_page"],
                end_page=r["topic_end_page"],
                lessons=[],
            )
            topics[t_id] = topic
            chapters[ch_id].topics.append(topic)

        if r["slot_id"] is None:
            continue
        topics[t_id].lessons.append(CurriculumLesson(
            id=uuid.UUID(str(r["slot_id"])),
            day_number=r["day_number"],
            title=r["topic_subtopic"],
            lesson_plan_id=uuid.UUID(str(r["lesson_plan_id"])) if r["lesson_plan_id"] else None,
            assessment_id=uuid.UUID(str(r["assessment_id"])) if r["assessment_id"] else None,
        ))

    logger.info("get_book_curriculum: book_id=%s chapters=%d", book.id, len(chapters))
    return BookCurriculumResponse(book_id=book.id, book_title=book.title, chapters=list(chapters.values()))


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
    logger.info("list_chapter_topics: chapter_id=%s", chapter_id)
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

    logger.info("list_chapter_topics: chapter_id=%s count=%d", chapter_id, total)
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
    logger.info("generate_slot_lp: slot_id=%s", slot_id)
    row = await db.execute(
        text("""
            SELECT
                ls.id, ls.lesson_plan_id,
                t.topic_text,
                ls.topic_subtopic AS topic,
                t.start_page, t.end_page,
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
        curriculum=data["curriculum"],
        grade=str(data["grade"]),
        subject=data["subject"],
        topic=data["topic"],
        page_number=_format_page_range(data["start_page"], data["end_page"]),
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

    async def _generate() -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from dars.mapping import canonical_grade, canonical_subject
        logger.info("_generate slot LP: lp_id=%s", lp_id)
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
                logger.error("_generate slot LP: lp_id=%s not found in DB", lp_id)
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
                logger.error("_generate slot LP: failed lp_id=%s", lp_id, exc_info=True)
                record.status = "ERROR"
            logger.info("_generate slot LP: done lp_id=%s status=%s", lp_id, record.status)
            await session.commit()
        await engine.dispose()

    logger.info("generate_slot_lp: queued background LP generation lp_id=%s", lp_id)
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

    slot_rows = await db.execute(
        select(LessonSlot)
        .where(LessonSlot.topic_id == topic_id)
        .order_by(LessonSlot.day_number)
    )
    slots = list(slot_rows.scalars().all())

    # Fetch assessment IDs for any slots that have a lesson_plan_id
    lp_ids = [s.lesson_plan_id for s in slots if s.lesson_plan_id is not None]
    assessment_map: dict = {}
    if lp_ids:
        from dars.assessments.models import Assessment as AssessmentModel
        from sqlalchemy import select as sa_select
        arows = await db.execute(
            sa_select(AssessmentModel.id, AssessmentModel.lesson_plan_id)
            .where(AssessmentModel.lesson_plan_id.in_(lp_ids))
        )
        assessment_map = {row.lesson_plan_id: row.id for row in arows}

    items = []
    for s in slots:
        data = {
            "id": s.id,
            "topic_id": s.topic_id,
            "day_number": s.day_number,
            "scheduled_date": s.scheduled_date,
            "topic_subtopic": s.topic_subtopic,
            "lesson_plan_id": s.lesson_plan_id,
            "assessment_id": assessment_map.get(s.lesson_plan_id) if s.lesson_plan_id else None,
            "created_at": s.created_at,
        }
        items.append(LessonSlotResponse(**data))
    return LessonSlotListResponse(items=items)


# ---------------------------------------------------------------------------
# Manual create / delete endpoints
# ---------------------------------------------------------------------------


class CreateTopicRequest(BaseModel):
    chapter_id: uuid.UUID
    topic_number: int
    title: str
    start_page: int | None = None
    end_page: int | None = None


class CreateSlotRequest(BaseModel):
    day_number: int
    topic_subtopic: str
    scheduled_date: str | None = None


@router.post("/api/v1/chapters/{chapter_id}/topics", response_model=TopicResponse, status_code=201)
async def create_topic(
    chapter_id: uuid.UUID,
    body: CreateTopicRequest,
    _admin: Client = Depends(get_admin_client),
    db: AsyncSession = Depends(get_db),
) -> TopicResponse:
    logger.info("create_topic: chapter_id=%s title=%r", chapter_id, body.title)
    from dars.curriculum.models import BookChapter
    chapter = await db.get(BookChapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    topic = Topic(
        chapter_id=chapter_id,
        topic_number=body.topic_number,
        title=body.title,
        start_page=body.start_page,
        end_page=body.end_page,
    )
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    logger.info("create_topic: done topic_id=%s", topic.id)
    return TopicResponse.model_validate(topic)


@router.post("/api/v1/topics/{topic_id}/slots", response_model=LessonSlotResponse, status_code=201)
async def create_slot(
    topic_id: uuid.UUID,
    body: CreateSlotRequest,
    _admin: Client = Depends(get_admin_client),
    db: AsyncSession = Depends(get_db),
) -> LessonSlotResponse:
    logger.info("create_slot: topic_id=%s day=%s", topic_id, body.day_number)
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    slot = LessonSlot(
        topic_id=topic_id,
        day_number=body.day_number,
        topic_subtopic=body.topic_subtopic,
        scheduled_date=body.scheduled_date,
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)
    logger.info("create_slot: done slot_id=%s", slot.id)
    return LessonSlotResponse.model_validate(slot)


@router.delete("/api/v1/chapters/{chapter_id}/breakdown", status_code=204)
async def delete_chapter_breakdown(
    chapter_id: uuid.UUID,
    _admin: Client = Depends(get_admin_client),
    db: AsyncSession = Depends(get_db),
) -> None:
    logger.info("delete_chapter_breakdown: chapter_id=%s", chapter_id)
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(Topic).where(Topic.chapter_id == chapter_id))
    await db.commit()
    logger.info("delete_chapter_breakdown: done chapter_id=%s", chapter_id)


@router.delete("/api/v1/topics/{topic_id}", status_code=204)
async def delete_topic(
    topic_id: uuid.UUID,
    _admin: Client = Depends(get_admin_client),
    db: AsyncSession = Depends(get_db),
) -> None:
    logger.info("delete_topic: topic_id=%s", topic_id)
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    await db.delete(topic)
    await db.commit()
    logger.info("delete_topic: done topic_id=%s", topic_id)


@router.delete("/api/v1/slots/{slot_id}", status_code=204)
async def delete_slot(
    slot_id: uuid.UUID,
    _admin: Client = Depends(get_admin_client),
    db: AsyncSession = Depends(get_db),
) -> None:
    logger.info("delete_slot: slot_id=%s", slot_id)
    slot = await db.get(LessonSlot, slot_id)
    if slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
    await db.delete(slot)
    await db.commit()
    logger.info("delete_slot: done slot_id=%s", slot_id)


@router.delete("/api/v1/lesson-plans/{lp_id}", status_code=204)
async def delete_lesson_plan(
    lp_id: uuid.UUID,
    _admin: Client = Depends(get_admin_client),
    db: AsyncSession = Depends(get_db),
) -> None:
    logger.info("delete_lesson_plan: lp_id=%s", lp_id)
    lp = await db.get(LessonPlan, lp_id)
    if lp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson plan not found")
    # Unlink from any slots pointing to this LP
    await db.execute(
        text("UPDATE lesson_slots SET lesson_plan_id = NULL WHERE lesson_plan_id = :lp_id"),
        {"lp_id": str(lp_id)},
    )
    await db.delete(lp)
    await db.commit()
    logger.info("delete_lesson_plan: done lp_id=%s", lp_id)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/chapters/{chapter_id}/breakdown",
    response_model=BreakdownResponse,
    dependencies=[Depends(get_admin_client)],
)
@admin_router.post(
    "/chapters/{chapter_id}/breakdown",
    response_model=BreakdownResponse,
    dependencies=[Depends(get_admin_client)],
)
async def breakdown_chapter_endpoint(
    chapter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BreakdownResponse:
    logger.info("breakdown_chapter_endpoint: chapter_id=%s", chapter_id)
    try:
        summary = await breakdown_chapter(db, chapter_id)
    except ValueError as exc:
        logger.error("breakdown_chapter_endpoint: error chapter_id=%s: %s", chapter_id, exc)
        status_code = (
            status.HTTP_500_INTERNAL_SERVER_ERROR
            if "not configured" in str(exc)
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("breakdown_chapter_endpoint: failed chapter_id=%s", chapter_id, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    logger.info(
        "breakdown_chapter_endpoint: done chapter_id=%s topics=%s slots=%s",
        chapter_id, summary.get("topics"), summary.get("slots"),
    )
    return BreakdownResponse(**summary)


@admin_router.get("/known-books", response_model=KnownBooksResponse)
async def known_books_endpoint(
    _admin: Client = Depends(get_admin_client),
) -> KnownBooksResponse:
    return KnownBooksResponse(items=[KnownBookEntry(**b) for b in list_known_books()])


@admin_router.post("/import-books", response_model=ImportBooksResponse)
async def import_books_endpoint(
    body: ImportBooksRequest,
    _admin: Client = Depends(get_admin_client),
    db: AsyncSession = Depends(get_db),
) -> ImportBooksResponse:
    logger.info(
        "import_books_endpoint: schema_filter=%s core_book_ids=%s",
        body.schema_filter, body.core_book_ids,
    )
    try:
        result = await import_books(db, schema_filter=body.schema_filter, core_book_ids=body.core_book_ids)
    except ValueError as exc:
        logger.error("import_books_endpoint: config error: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("import_books_endpoint: failed", exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Import failed") from exc
    logger.info("import_books_endpoint: done result=%s", result)
    return ImportBooksResponse(**result)


@admin_router.get("/preview-book", response_model=BookPreviewResponse)
async def preview_book_endpoint(
    core_id: int = Query(...),
    schema: str = Query(...),
    _admin: Client = Depends(get_admin_client),
) -> BookPreviewResponse:
    """Fetch book info from core DB without importing anything."""
    logger.info("preview_book_endpoint: core_id=%s schema=%s", core_id, schema)
    if schema not in ("fde_staging", "balochistan_staging"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid schema")
    try:
        data = await preview_book(core_id=core_id, schema=schema)
    except ValueError as exc:
        logger.error("preview_book_endpoint: config error: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("preview_book_endpoint: core DB error", exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Core DB error: {exc}") from exc
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Book {core_id} not found in {schema}")
    logger.info(
        "preview_book_endpoint: done core_id=%s title=%r chapters=%d",
        core_id, data["title"], len(data["chapters"]),
    )
    return BookPreviewResponse(
        **{k: v for k, v in data.items() if k != "chapters"},
        chapters=[ChapterPreview(**ch) for ch in data["chapters"]],
    )


@admin_router.post("/import-book", response_model=ImportSingleBookResponse)
async def import_single_book_endpoint(
    body: ImportSingleBookRequest,
    _admin: Client = Depends(get_admin_client),
    db: AsyncSession = Depends(get_db),
) -> ImportSingleBookResponse:
    """Import a single book with OCR (book_text) into Dars."""
    logger.info(
        "import_single_book_endpoint: core_id=%s schema=%s curriculum=%s grade=%s subject=%s",
        body.core_id, body.schema, body.curriculum, body.grade, body.subject,
    )
    if body.schema not in ("fde_staging", "balochistan_staging"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid schema")
    try:
        result = await import_single_book(
            db,
            core_id=body.core_id,
            schema=body.schema,
            curriculum=body.curriculum,
            grade=body.grade,
            subject=body.subject,
        )
    except ValueError as exc:
        logger.error("import_single_book_endpoint: error: %s", exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("import_single_book_endpoint: failed", exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Import failed: {exc}") from exc
    logger.info(
        "import_single_book_endpoint: done core_id=%s status=%s chapters=%d",
        body.core_id, result["status"], result["chapters"],
    )
    return ImportSingleBookResponse(**result)


@admin_router.post("/chapters/{chapter_id}/generate-lps")
async def bulk_generate_lps_endpoint(
    chapter_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    force: bool = Query(default=False),
    _admin: Client = Depends(get_admin_client),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Queue LP generation for all slots in a chapter that have topic_text."""
    logger.info("bulk_generate_lps_endpoint: chapter_id=%s force=%s", chapter_id, force)
    rows = await db.execute(
        text("""
            SELECT ls.id AS slot_id, ls.lesson_plan_id, t.topic_text,
                   ls.topic_subtopic AS topic, t.start_page, t.end_page,
                   b.grade, b.subject, b.curriculum
            FROM lesson_slots ls
            JOIN topics t ON t.id = ls.topic_id
            JOIN book_chapters bc ON bc.id = t.chapter_id
            JOIN books b ON b.id = bc.book_id
            WHERE t.chapter_id = :chapter_id
        """),
        {"chapter_id": str(chapter_id)},
    )
    slots = rows.mappings().all()

    queued = skipped = 0
    for slot in slots:
        if not slot["topic_text"]:
            skipped += 1
            continue
        if slot["lesson_plan_id"] and not force:
            skipped += 1
            continue

        lp = LessonPlan(
            curriculum=slot["curriculum"],
            grade=str(slot["grade"]),
            subject=slot["subject"],
            topic=slot["topic"],
            page_number=_format_page_range(slot["start_page"], slot["end_page"]),
            status="PENDING",
        )
        db.add(lp)
        await db.flush()
        await db.execute(
            text("UPDATE lesson_slots SET lesson_plan_id = :lp_id WHERE id = :slot_id"),
            {"lp_id": str(lp.id), "slot_id": str(slot["slot_id"])},
        )
        slot_data = dict(slot)
        lp_id = lp.id

        async def _generate(sd=slot_data, lid=lp_id) -> None:
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
            from dars.mapping import canonical_grade, canonical_subject
            logger.info("_generate bulk LP: lp_id=%s topic=%s", lid, sd.get("topic"))
            engine = create_async_engine(settings.database_url)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            payload = {
                "grade": canonical_grade(sd["grade"]),
                "curriculum": sd["curriculum"],
                "subject": canonical_subject(sd["subject"]),
                "topic": sd["topic"],
                "page_content": sd["topic_text"] or "",
            }
            async with factory() as session:
                record = await session.get(LessonPlan, lid)
                if record is None:
                    logger.error("_generate bulk LP: lp_id=%s not found in DB", lid)
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
                    logger.error("_generate bulk LP: failed lp_id=%s", lid, exc_info=True)
                    record.status = "ERROR"
                logger.info("_generate bulk LP: done lp_id=%s status=%s", lid, record.status)
                await session.commit()
            await engine.dispose()

        background_tasks.add_task(_generate)
        queued += 1

    await db.commit()
    logger.info("bulk_generate_lps_endpoint: done chapter_id=%s queued=%d skipped=%d", chapter_id, queued, skipped)
    return {"queued": queued, "skipped": skipped}


@admin_router.post("/books/{book_id}/build-remaining")
async def build_remaining_endpoint(
    book_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    chapter_id: uuid.UUID | None = None,
    _admin: Client = Depends(get_admin_client),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Background task: run breakdown → LPs → quizzes, skipping anything already done.
    If chapter_id is provided, only that chapter is processed; otherwise all chapters
    in the book are processed.
    """
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    if chapter_id is not None:
        chapter = await db.get(BookChapter, chapter_id)
        if chapter is None or chapter.book_id != book_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
        chapter_ids = [chapter_id]
    else:
        chapters = await list_book_chapters(db, book_id=book_id)
        chapter_ids = [c.id for c in chapters]

    logger.info("build_remaining_endpoint: book_id=%s chapters=%d", book_id, len(chapter_ids))

    async def _build_all() -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from dars.assessments.models import Assessment
        from dars.assessments.service import generate_assessment
        from dars.mapping import canonical_grade, canonical_subject

        engine = create_async_engine(settings.database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        for chapter_id in chapter_ids:
            logger.info("build_remaining: processing chapter_id=%s", chapter_id)
            async with factory() as session:
                try:
                    # Step 1: breakdown if no topics
                    topic_count_row = await session.execute(
                        text("SELECT COUNT(*) FROM topics WHERE chapter_id = :cid"),
                        {"cid": str(chapter_id)},
                    )
                    topic_count = topic_count_row.scalar()
                    if topic_count == 0:
                        logger.info("build_remaining: running breakdown for chapter_id=%s", chapter_id)
                        await breakdown_chapter(session, chapter_id)
                    else:
                        logger.info("build_remaining: breakdown already done chapter_id=%s topics=%d", chapter_id, topic_count)

                    # Step 2: generate LPs for slots without one
                    slot_rows = await session.execute(
                        text("""
                            SELECT ls.id AS slot_id, ls.lesson_plan_id,
                                   t.topic_text, ls.topic_subtopic AS topic,
                                   t.start_page, t.end_page,
                                   b.grade, b.subject, b.curriculum
                            FROM lesson_slots ls
                            JOIN topics t ON t.id = ls.topic_id
                            JOIN book_chapters bc ON bc.id = t.chapter_id
                            JOIN books b ON b.id = bc.book_id
                            WHERE t.chapter_id = :cid AND ls.lesson_plan_id IS NULL
                              AND t.topic_text IS NOT NULL AND t.topic_text != ''
                        """),
                        {"cid": str(chapter_id)},
                    )
                    slots_needing_lp = slot_rows.mappings().all()
                    logger.info("build_remaining: chapter_id=%s slots needing LP=%d", chapter_id, len(slots_needing_lp))

                    for slot in slots_needing_lp:
                        lp = LessonPlan(
                            curriculum=slot["curriculum"],
                            grade=str(slot["grade"]),
                            subject=slot["subject"],
                            topic=slot["topic"],
                            page_number=_format_page_range(slot["start_page"], slot["end_page"]),
                            status="PENDING",
                        )
                        session.add(lp)
                        await session.flush()
                        await session.execute(
                            text("UPDATE lesson_slots SET lesson_plan_id = :lp_id WHERE id = :slot_id"),
                            {"lp_id": str(lp.id), "slot_id": str(slot["slot_id"])},
                        )
                        await session.commit()

                        # Generate LP synchronously (wait for it before moving on)
                        payload = {
                            "grade": canonical_grade(slot["grade"]),
                            "curriculum": slot["curriculum"],
                            "subject": canonical_subject(slot["subject"]),
                            "topic": slot["topic"],
                            "page_content": slot["topic_text"] or "",
                        }
                        try:
                            async with httpx.AsyncClient(timeout=120.0) as http:
                                resp = await http.post(
                                    f"{settings.lp_assistant_url}/api/generate-lp",
                                    json=payload,
                                    headers={"api-key": settings.lp_assistant_api_key},
                                )
                            resp.raise_for_status()
                            result = resp.json()
                            async with factory() as upd:
                                record = await upd.get(LessonPlan, lp.id)
                                if record:
                                    record.content = result.get("lesson_plan", "")
                                    record.content_bilingual = result.get("lesson_plan_bilingual")
                                    record.tags = result.get("tags") or {}
                                    record.metadata_ = result.get("metadata") or {}
                                    record.status = "READY"
                                    await upd.commit()
                        except Exception:
                            logger.error("build_remaining: LP generation failed slot_id=%s", slot["slot_id"], exc_info=True)
                            async with factory() as upd:
                                record = await upd.get(LessonPlan, lp.id)
                                if record:
                                    record.status = "ERROR"
                                    await upd.commit()

                    # Step 3: generate quizzes for LPs without assessments
                    quiz_rows = await session.execute(
                        text("""
                            SELECT ls.lesson_plan_id
                            FROM lesson_slots ls
                            JOIN topics t ON t.id = ls.topic_id
                            LEFT JOIN assessments a ON a.lesson_plan_id = ls.lesson_plan_id
                            WHERE t.chapter_id = :cid
                              AND ls.lesson_plan_id IS NOT NULL
                              AND a.id IS NULL
                        """),
                        {"cid": str(chapter_id)},
                    )
                    lps_needing_quiz = [r[0] for r in quiz_rows]
                    logger.info("build_remaining: chapter_id=%s LPs needing quiz=%d", chapter_id, len(lps_needing_quiz))

                    for lp_id in lps_needing_quiz:
                        async with factory() as qs:
                            assessment = Assessment(lesson_plan_id=lp_id, status="PENDING")
                            qs.add(assessment)
                            await qs.flush()
                            assessment_id = assessment.id
                            await qs.commit()
                        await generate_assessment(assessment_id, lp_id, settings.database_url)

                except Exception:
                    logger.error("build_remaining: chapter_id=%s failed", chapter_id, exc_info=True)

        await engine.dispose()
        logger.info("build_remaining: book_id=%s done", book_id)

    background_tasks.add_task(_build_all)
    logger.info("build_remaining_endpoint: queued background task book_id=%s chapters=%d", book_id, len(chapter_ids))
    return {"status": "started", "chapters": len(chapter_ids)}
