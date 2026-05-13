import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.curriculum_data.models import CurriculumData
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


async def resolve_grade_id(db: AsyncSession, code: int) -> int:
    """Return grades.id for the given grade code. Raises 422 if not found."""
    grade = await validate_grade(db, code)
    return grade.id


async def resolve_subject_id(db: AsyncSession, code: str) -> int:
    """Return subjects.id for the given subject code. Raises 422 if not found."""
    subject = await validate_subject(db, code)
    return subject.id


async def resolve_curriculum_id(db: AsyncSession, code: str) -> int:
    """Return curriculums.id for the given curriculum code. Raises 422 if not found."""
    result = await db.execute(select(CurriculumData).where(CurriculumData.code == code))
    curriculum = result.scalar_one_or_none()
    if curriculum is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid curriculum: {code!r}.",
        )
    return curriculum.id


async def get_grade_code(db: AsyncSession, grade_id: int) -> int | None:
    """Return grade code (integer) for a grades.id, or None if not found."""
    result = await db.execute(select(Grade).where(Grade.id == grade_id))
    row = result.scalar_one_or_none()
    return row.code if row else None


async def get_subject_code(db: AsyncSession, subject_id: int) -> str | None:
    """Return subject code (string) for a subjects.id, or None if not found."""
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    row = result.scalar_one_or_none()
    return row.code if row else None


async def get_curriculum_code(db: AsyncSession, curriculum_id: int) -> str | None:
    """Return curriculum code (string) for a curriculums.id, or None if not found."""
    result = await db.execute(select(CurriculumData).where(CurriculumData.id == curriculum_id))
    row = result.scalar_one_or_none()
    return row.code if row else None
