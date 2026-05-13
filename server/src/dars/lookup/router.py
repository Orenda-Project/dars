import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dars.database import get_db
from dars.lookup.schemas import GradeResponse, SubjectResponse
from dars.lookup.service import get_all_grades, get_all_subjects

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["lookup"])


@router.get("/grades", response_model=list[GradeResponse])
async def list_grades(db: AsyncSession = Depends(get_db)) -> list[GradeResponse]:
    logger.info("list_grades")
    return await get_all_grades(db)


@router.get("/subjects", response_model=list[SubjectResponse])
async def list_subjects(db: AsyncSession = Depends(get_db)) -> list[SubjectResponse]:
    logger.info("list_subjects")
    return await get_all_subjects(db)
