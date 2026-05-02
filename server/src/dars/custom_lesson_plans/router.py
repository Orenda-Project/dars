import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.database import get_db
from dars.deps import get_current_client
from dars.custom_lesson_plans.schemas import (
    CustomLessonPlanCreateRequest,
    CustomLessonPlanListResponse,
    CustomLessonPlanResponse,
)
from dars.custom_lesson_plans.service import (
    generate_custom_lesson_plan_task,
    get_custom_lesson_plan,
    list_custom_lesson_plans,
    queue_custom_lesson_plan,
)

router = APIRouter(prefix="/api/v1/custom-lesson-plans", tags=["custom-lesson-plans"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CustomLessonPlanResponse,
)
async def create_custom_lesson_plan(
    body: CustomLessonPlanCreateRequest,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> CustomLessonPlanResponse:
    """
    Queue a custom lesson plan for async generation.

    Curriculum is taken from the authenticated client's profile.
    Returns immediately with status=PENDING and a lesson plan id.
    Poll GET /api/v1/custom-lesson-plans/{id} to check status.
    """
    if not current_client.curriculum:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Client has no curriculum configured. Contact support to set one.",
        )

    lp = await queue_custom_lesson_plan(
        db,
        client_id=current_client.id,
        curriculum=current_client.curriculum,
        request=body,
    )
    background_tasks.add_task(
        generate_custom_lesson_plan_task,
        lp_id=lp.id,
        client_id=current_client.id,
        curriculum=current_client.curriculum,
        request=body,
    )
    return CustomLessonPlanResponse.model_validate(lp)


@router.get(
    "",
    response_model=CustomLessonPlanListResponse,
)
async def list_custom_lesson_plans_endpoint(
    external_id: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> CustomLessonPlanListResponse:
    """List all custom lesson plans for the authenticated client."""
    items, total = await list_custom_lesson_plans(
        db,
        client_id=current_client.id,
        external_id=external_id,
        offset=offset,
        limit=limit,
    )
    return CustomLessonPlanListResponse(
        items=[CustomLessonPlanResponse.model_validate(lp) for lp in items],
        total=total,
    )


@router.get(
    "/{lp_id}",
    response_model=CustomLessonPlanResponse,
)
async def get_custom_lesson_plan_endpoint(
    lp_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> CustomLessonPlanResponse:
    """Get a single custom lesson plan by id. Only accessible to the owning client."""
    lp = await get_custom_lesson_plan(db, client_id=current_client.id, lp_id=lp_id)
    if lp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom lesson plan not found",
        )
    return CustomLessonPlanResponse.model_validate(lp)
