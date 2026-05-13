import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.lookup.models import Grade, Subject

logger = logging.getLogger(__name__)


async def get_all_grades(db: AsyncSession) -> list[Grade]:
    logger.info("get_all_grades")
    result = await db.execute(select(Grade).order_by(Grade.code))
    return list(result.scalars().all())


async def get_all_subjects(db: AsyncSession) -> list[Subject]:
    logger.info("get_all_subjects")
    result = await db.execute(select(Subject).order_by(Subject.code))
    return list(result.scalars().all())


async def validate_grade(db: AsyncSession, code: int) -> Grade:
    result = await db.execute(select(Grade).where(Grade.code == code))
    grade = result.scalar_one_or_none()
    if grade is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid grade: {code}. Call GET /api/v1/grades for valid values.",
        )
    return grade


async def validate_subject(db: AsyncSession, code: str) -> Subject:
    result = await db.execute(select(Subject).where(Subject.code == code))
    subject = result.scalar_one_or_none()
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid subject: {code!r}. Call GET /api/v1/subjects for valid values.",
        )
    return subject
