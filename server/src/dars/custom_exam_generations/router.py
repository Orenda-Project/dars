import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.database import get_db
from dars.deps import get_current_client
from dars.custom_exam_generations.schemas import (
    CustomExamGenerationCreateRequest,
    CustomExamGenerationListResponse,
    CustomExamGenerationResponse,
)
from dars.custom_exam_generations.service import (
    generate_custom_exam_task,
    get_custom_exam_generation,
    list_custom_exam_generations,
    queue_custom_exam_generation,
)

router = APIRouter(prefix="/api/v1/custom-exam-generations", tags=["custom-exam-generations"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CustomExamGenerationResponse,
)
async def create_custom_exam_generation(
    body: CustomExamGenerationCreateRequest,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> CustomExamGenerationResponse:
    """
    Queue a custom exam generation for async generation.

    Curriculum is taken from the authenticated client's profile.
    Returns immediately with status=PENDING and an exam generation id.
    Poll GET /api/v1/custom-exam-generations/{id} to check status.
    """
    if not current_client.curriculum:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Client has no curriculum configured. Contact support to set one.",
        )

    eg = await queue_custom_exam_generation(
        db,
        client_id=current_client.id,
        curriculum=current_client.curriculum,
        request=body,
    )
    background_tasks.add_task(
        generate_custom_exam_task,
        eg_id=eg.id,
        client_id=current_client.id,
        curriculum=current_client.curriculum,
        request=body,
    )
    return CustomExamGenerationResponse.model_validate(eg)


@router.get(
    "",
    response_model=CustomExamGenerationListResponse,
)
async def list_custom_exam_generations_endpoint(
    external_id: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> CustomExamGenerationListResponse:
    """List all custom exam generations for the authenticated client."""
    items, total = await list_custom_exam_generations(
        db,
        client_id=current_client.id,
        external_id=external_id,
        offset=offset,
        limit=limit,
    )
    return CustomExamGenerationListResponse(
        items=[CustomExamGenerationResponse.model_validate(eg) for eg in items],
        total=total,
    )


@router.get(
    "/{eg_id}",
    response_model=CustomExamGenerationResponse,
)
async def get_custom_exam_generation_endpoint(
    eg_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> CustomExamGenerationResponse:
    """Get a single custom exam generation by id. Only accessible to the owning client."""
    eg = await get_custom_exam_generation(db, client_id=current_client.id, eg_id=eg_id)
    if eg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom exam generation not found",
        )
    return CustomExamGenerationResponse.model_validate(eg)
