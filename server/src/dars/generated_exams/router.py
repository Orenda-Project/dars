import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.database import get_db
from dars.deps import get_current_client
from dars.generated_exams.schemas import GeneratedExamCreate, GeneratedExamListResponse, GeneratedExamResponse
from dars.generated_exams.service import create_generated_exam, get_generated_exam, generate_exam_task, list_generated_exams

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/exams", tags=["exams"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GeneratedExamResponse,
)
async def create_exam_endpoint(
    body: GeneratedExamCreate,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> GeneratedExamResponse:
    """
    Queue an exam for async generation.

    Curriculum is taken from the authenticated client's profile.
    Returns immediately with status=PENDING and an exam id.
    Poll GET /api/v1/exams/{id} to check status.
    """
    logger.info(
        "create_exam_endpoint: client_id=%s grade=%s subject=%s",
        current_client.id, body.grade, body.subject,
    )
    if not current_client.curriculum:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Client has no curriculum configured.",
        )

    exam = await create_generated_exam(
        db,
        client_id=current_client.id,
        data=body,
        curriculum=current_client.curriculum,
    )
    background_tasks.add_task(
        generate_exam_task,
        exam_id=exam.id,
        client_id=current_client.id,
        curriculum=current_client.curriculum,
        request=body,
    )
    logger.info("create_exam_endpoint: queued exam_id=%s client_id=%s", exam.id, current_client.id)
    return GeneratedExamResponse.model_validate(exam)


@router.get(
    "",
    response_model=GeneratedExamListResponse,
)
async def list_exams_endpoint(
    external_id: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> GeneratedExamListResponse:
    """List all generated exams for the authenticated client."""
    logger.info("list_exams_endpoint: client_id=%s", current_client.id)
    items, total = await list_generated_exams(
        db,
        client_id=current_client.id,
        external_id=external_id,
        skip=offset,
        limit=limit,
    )
    logger.info("list_exams_endpoint: client_id=%s total=%d", current_client.id, total)
    return GeneratedExamListResponse(
        items=[GeneratedExamResponse.model_validate(exam) for exam in items],
        total=total,
    )


@router.get(
    "/{exam_id}",
    response_model=GeneratedExamResponse,
)
async def get_exam_endpoint(
    exam_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> GeneratedExamResponse:
    """Get a single generated exam by id. Only accessible to the owning client."""
    logger.info("get_exam_endpoint: exam_id=%s client_id=%s", exam_id, current_client.id)
    exam = await get_generated_exam(db, exam_id=exam_id, client_id=current_client.id)
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )
    return GeneratedExamResponse.model_validate(exam)
