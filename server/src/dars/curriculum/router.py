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
    BookListResponse,
    BookPreviewResponse,
    BookResponse,
    BreakdownResponse,
    ChapterPreview,
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
    logger.info("generate_slot_lp: slot_id=%s client_id=%s", slot_id, current_client.id)
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
        client_id=current_client.id,
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
    client_id = current_client.id

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

    result = await db.execute(
        select(LessonSlot)
        .where(LessonSlot.topic_id == topic_id)
        .order_by(LessonSlot.day_number)
    )
    items = list(result.scalars().all())
    return LessonSlotListResponse(items=[LessonSlotResponse.model_validate(s) for s in items])


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
            client_id=_admin.id,
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
        admin_id = _admin.id

        async def _generate(sd=slot_data, lid=lp_id, aid=admin_id) -> None:
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
