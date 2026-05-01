import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.database import get_db
from dars.deps import get_current_client
from dars.exam_generations.schemas import (
    ExamGenerationCreateRequest,
    ExamGenerationListResponse,
    ExamGenerationResponse,
)
from dars.exam_generations.service import (
    generate_exam_task,
    get_exam_generation,
    list_exam_generations,
    queue_exam_generation,
)

router = APIRouter(prefix="/api/v1/exam-generations", tags=["exam-generations"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ExamGenerationResponse,
)
async def create_exam_generation(
    body: ExamGenerationCreateRequest,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> ExamGenerationResponse:
    """
    Queue an exam generation for async generation.

    Returns immediately with status=PENDING and an exam generation id.
    Poll GET /api/v1/exam-generations/{id} or wait for the webhook.
    """
    eg = await queue_exam_generation(db, client_id=current_client.id, request=body)
    background_tasks.add_task(
        generate_exam_task,
        eg_id=eg.id,
        client_id=current_client.id,
        request=body,
    )
    return ExamGenerationResponse.model_validate(eg)


@router.get(
    "",
    response_model=ExamGenerationListResponse,
)
async def list_exam_generations_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> ExamGenerationListResponse:
    """List all exam generations for the authenticated client."""
    items, total = await list_exam_generations(db, client_id=current_client.id, offset=offset, limit=limit)
    return ExamGenerationListResponse(
        items=[ExamGenerationResponse.model_validate(eg) for eg in items],
        total=total,
    )


@router.get(
    "/{eg_id}",
    response_model=ExamGenerationResponse,
)
async def get_exam_generation_endpoint(
    eg_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> ExamGenerationResponse:
    """Get a single exam generation by id. Only accessible to the owning client."""
    eg = await get_exam_generation(db, client_id=current_client.id, eg_id=eg_id)
    if eg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam generation not found")
    return ExamGenerationResponse.model_validate(eg)
