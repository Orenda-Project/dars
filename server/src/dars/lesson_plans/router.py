import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.database import get_db
from dars.deps import get_current_client
from dars.lesson_plans.schemas import (
    LessonPlanCreateRequest,
    LessonPlanListResponse,
    LessonPlanResponse,
)
from dars.lesson_plans.service import (
    generate_lesson_plan_task,
    get_lesson_plan,
    list_lesson_plans,
    queue_lesson_plan,
)

router = APIRouter(prefix="/api/v1/lesson-plans", tags=["lesson-plans"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=LessonPlanResponse,
)
async def create_lesson_plan(
    body: LessonPlanCreateRequest,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    """
    Queue a lesson plan for async generation.

    Returns immediately with status=PENDING and a lesson plan id.
    Poll GET /api/v1/lesson-plans/{id} or wait for the webhook.
    """
    lp = await queue_lesson_plan(db, request=body)
    background_tasks.add_task(
        generate_lesson_plan_task,
        lp_id=lp.id,
        request=body,
    )
    return LessonPlanResponse.model_validate(lp)


@router.get(
    "",
    response_model=LessonPlanListResponse,
)
async def list_lesson_plans_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanListResponse:
    """List all lesson plans for the authenticated client."""
    items, total = await list_lesson_plans(db, offset=offset, limit=limit)
    return LessonPlanListResponse(
        items=[LessonPlanResponse.model_validate(lp) for lp in items],
        total=total,
    )


@router.get(
    "/{lp_id}",
    response_model=LessonPlanResponse,
)
async def get_lesson_plan_endpoint(
    lp_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    """Get a single lesson plan by id. Only accessible to the owning client."""
    lp = await get_lesson_plan(db, lp_id=lp_id)
    if lp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson plan not found")
    return lp


