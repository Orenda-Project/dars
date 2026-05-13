import logging

from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.curriculum.models import Book, BookChapter, CurriculumChapterSchedule, SLO, TopicSLO

logger = logging.getLogger(__name__)


async def list_slos(
    db: AsyncSession,
    curriculum: str,
    grade: int | None = None,
    subject: str | None = None,
) -> tuple[list[SLO], int]:
    query = select(SLO).where(SLO.curriculum == curriculum)
    if grade is not None:
        query = query.where(SLO.grade == grade)
    if subject is not None:
        query = query.where(SLO.subject == subject)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    items_result = await db.execute(query.order_by(SLO.grade, SLO.subject, SLO.code))
    return list(items_result.scalars().all()), total


async def get_topic_slos(db: AsyncSession, topic_id: int) -> list[SLO]:
    result = await db.execute(
        select(SLO)
        .join(TopicSLO, TopicSLO.slo_id == SLO.id)
        .where(TopicSLO.topic_id == topic_id)
        .order_by(SLO.code)
    )
    return list(result.scalars().all())


async def import_slos(
    db: AsyncSession,
    curriculum: str,
    slos_data: list[dict],
) -> dict[str, int]:
    imported = updated = 0
    for item in slos_data:
        existing = await db.execute(
            select(SLO).where(SLO.curriculum == curriculum, SLO.code == item["code"])
        )
        row = existing.scalar_one_or_none()
        if row is None:
            db.add(SLO(
                curriculum=curriculum,
                grade=item["grade"],
                subject=item["subject"],
                code=item["code"],
                description=item["description"],
            ))
            imported += 1
        else:
            row.grade = item["grade"]
            row.subject = item["subject"]
            row.description = item["description"]
            updated += 1
    await db.commit()
    logger.info("import_slos: curriculum=%s imported=%d updated=%d", curriculum, imported, updated)
    return {"imported": imported, "updated": updated}


async def map_topic_slos(
    db: AsyncSession,
    topic_id: int,
    slo_codes: list[str],
    curriculum: str,
) -> int:
    slo_result = await db.execute(
        select(SLO).where(SLO.curriculum == curriculum, SLO.code.in_(slo_codes))
    )
    slos = list(slo_result.scalars().all())
    found_codes = {s.code for s in slos}
    missing = set(slo_codes) - found_codes
    if missing:
        raise ValueError(f"Unknown SLO codes for curriculum {curriculum}: {sorted(missing)}")

    for slo in slos:
        existing = await db.execute(
            select(TopicSLO).where(TopicSLO.topic_id == topic_id, TopicSLO.slo_id == slo.id)
        )
        if existing.scalar_one_or_none() is None:
            db.add(TopicSLO(topic_id=topic_id, slo_id=slo.id))
    await db.commit()
    logger.info("map_topic_slos: topic_id=%s mapped=%d", topic_id, len(slos))
    return len(slos)


async def clear_topic_slos(db: AsyncSession, topic_id: int) -> None:
    await db.execute(sa_delete(TopicSLO).where(TopicSLO.topic_id == topic_id))
    await db.commit()
    logger.info("clear_topic_slos: topic_id=%s cleared", topic_id)


async def list_books(
    db: AsyncSession,
    curriculum: str | None = None,
    grade: int | None = None,
    subject: str | None = None,
) -> tuple[list[Book], int]:
    query = select(Book)
    if curriculum is not None:
        query = query.where(Book.curriculum == curriculum)
    if grade is not None:
        query = query.where(Book.grade == grade)
    if subject is not None:
        query = query.where(Book.subject == subject)

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    items_result = await db.execute(query.order_by(Book.created_at.desc()))
    items = list(items_result.scalars().all())
    return items, total


async def list_book_chapters(
    db: AsyncSession,
    book_id: int,
) -> list[BookChapter]:
    result = await db.execute(
        select(BookChapter)
        .where(BookChapter.book_id == book_id)
        .order_by(BookChapter.chapter_number)
    )
    return list(result.scalars().all())


async def upsert_chapter_schedule(
    db: AsyncSession,
    curriculum: str,
    items: list,
) -> list[CurriculumChapterSchedule]:
    logger.info("upsert_chapter_schedule: curriculum=%s count=%d", curriculum, len(items))
    upserted: list[CurriculumChapterSchedule] = []
    for item in items:
        existing_result = await db.execute(
            select(CurriculumChapterSchedule).where(
                CurriculumChapterSchedule.curriculum == curriculum,
                CurriculumChapterSchedule.chapter_id == item.chapter_id,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            existing.book_id = item.book_id
            existing.suggested_teaching_days = item.suggested_teaching_days
            existing.suggested_position = item.suggested_position
            existing.term = item.term
            await db.flush()
            await db.refresh(existing)
            upserted.append(existing)
        else:
            row = CurriculumChapterSchedule(
                curriculum=curriculum,
                book_id=item.book_id,
                chapter_id=item.chapter_id,
                suggested_teaching_days=item.suggested_teaching_days,
                suggested_position=item.suggested_position,
                term=item.term,
            )
            db.add(row)
            await db.flush()
            await db.refresh(row)
            upserted.append(row)
    await db.commit()
    logger.info("upsert_chapter_schedule: curriculum=%s upserted=%d", curriculum, len(upserted))
    return upserted


async def list_chapter_schedule(
    db: AsyncSession,
    curriculum: str,
) -> list[CurriculumChapterSchedule]:
    logger.info("list_chapter_schedule: curriculum=%s", curriculum)
    result = await db.execute(
        select(CurriculumChapterSchedule)
        .where(CurriculumChapterSchedule.curriculum == curriculum)
        .order_by(CurriculumChapterSchedule.suggested_position)
    )
    items = list(result.scalars().all())
    logger.info("list_chapter_schedule: curriculum=%s count=%d", curriculum, len(items))
    return items
