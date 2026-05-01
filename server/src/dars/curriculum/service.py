import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.curriculum.models import Book, BookChapter


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
    book_id: uuid.UUID,
) -> list[BookChapter]:
    result = await db.execute(
        select(BookChapter)
        .where(BookChapter.book_id == book_id)
        .order_by(BookChapter.chapter_number)
    )
    return list(result.scalars().all())
