import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.assessments.models import Assessment
from dars.assessments.schemas import AssessmentResponse
from dars.assessments.service import generate_assessment
from dars.clients.models import Client
from dars.config import settings
from dars.database import get_db
from dars.deps import get_current_client
from dars.lesson_plans.models import LessonPlan

logger = logging.getLogger(__name__)

router = APIRouter(tags=["assessments"])


@router.post(
    "/api/v1/lesson-plans/{lp_id}/assessment",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_or_replace_assessment(
    lp_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    """Generate (or regenerate) an assessment for a lesson plan. Replaces any existing one."""
    logger.info("create_or_replace_assessment: lp_id=%s client_id=%s", lp_id, current_client.id)

    lp = await db.get(LessonPlan, lp_id)
    if lp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson plan not found")

    existing_result = await db.execute(
        select(Assessment).where(Assessment.lesson_plan_id == lp_id)
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        logger.info("create_or_replace_assessment: deleting existing assessment_id=%s", existing.id)
        await db.delete(existing)
        await db.flush()

    assessment = Assessment(lesson_plan_id=lp_id, status="PENDING")
    db.add(assessment)
    await db.flush()
    assessment_id = assessment.id
    await db.commit()
    await db.refresh(assessment)

    background_tasks.add_task(
        generate_assessment,
        assessment_id=assessment_id,
        lesson_plan_id=lp_id,
        db_url=settings.database_url,
    )

    logger.info("create_or_replace_assessment: queued assessment_id=%s", assessment_id)
    return AssessmentResponse.model_validate(assessment)


@router.get(
    "/api/v1/assessments/{assessment_id}",
    response_model=AssessmentResponse,
)
async def get_assessment(
    assessment_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    logger.info("get_assessment: assessment_id=%s client_id=%s", assessment_id, current_client.id)

    assessment = await db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    logger.info("get_assessment: found assessment_id=%s status=%s", assessment_id, assessment.status)
    return AssessmentResponse.model_validate(assessment)
