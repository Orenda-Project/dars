import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.student_assessments.models import StudentAssessment
from dars.student_assessments.schemas import StudentAssessmentResponse
from dars.student_assessments.service import generate_student_assessment
from dars.clients.models import Client
from dars.config import settings
from dars.database import get_db
from dars.deps import get_current_client
from dars.lesson_plans.models import LessonPlan

logger = logging.getLogger(__name__)

router = APIRouter(tags=["student-assessments"])


@router.get(
    "/api/v1/lesson-plans/{lp_id}/student-assessment",
    response_model=StudentAssessmentResponse,
)
async def get_student_assessment_by_lp(
    lp_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> StudentAssessmentResponse:
    """Return the student assessment for a lesson plan, generating and persisting it on first fetch."""
    logger.info("get_student_assessment_by_lp: lp_id=%s client_id=%s", lp_id, current_client.id)

    lp = await db.get(LessonPlan, lp_id)
    if lp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson plan not found")

    existing_result = await db.execute(
        select(StudentAssessment).where(StudentAssessment.lesson_plan_id == lp_id)
    )
    assessment = existing_result.scalar_one_or_none()

    if assessment is None or assessment.status == "PENDING":
        if assessment is None:
            logger.info("get_student_assessment_by_lp: none found, generating lp_id=%s", lp_id)
            assessment = StudentAssessment(lesson_plan_id=lp_id, status="PENDING")
            db.add(assessment)
            await db.flush()
            await db.commit()
            await db.refresh(assessment)
        else:
            logger.info("get_student_assessment_by_lp: stale PENDING found, re-running generation assessment_id=%s", assessment.id)
        assessment_id = assessment.id
        await generate_student_assessment(assessment_id, lp_id, settings.database_url)
        await db.expire_all()
        assessment = await db.get(StudentAssessment, assessment_id)

    logger.info(
        "get_student_assessment_by_lp: lp_id=%s assessment_id=%s status=%s",
        lp_id, assessment.id, assessment.status,
    )
    return StudentAssessmentResponse.model_validate(assessment)


@router.get(
    "/api/v1/student-assessments/{assessment_id}",
    response_model=StudentAssessmentResponse,
)
async def get_student_assessment(
    assessment_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> StudentAssessmentResponse:
    logger.info("get_student_assessment: assessment_id=%s client_id=%s", assessment_id, current_client.id)

    assessment = await db.get(StudentAssessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student assessment not found")

    logger.info("get_student_assessment: found assessment_id=%s status=%s", assessment_id, assessment.status)
    return StudentAssessmentResponse.model_validate(assessment)
