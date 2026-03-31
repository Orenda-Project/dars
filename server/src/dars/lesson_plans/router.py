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


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=LessonPlanResponse)
async def create_lesson_plan_endpoint(
    body: LessonPlanCreateRequest,
    background_tasks: BackgroundTasks,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    lp = await queue_lesson_plan(db, client_id=current_client.id, request=body)
    background_tasks.add_task(
        generate_lesson_plan_task,
        lp_id=lp.id,
        client_id=current_client.id,
        webhook_url=current_client.webhook_url,
        request=body,
        db=db,
    )
    return LessonPlanResponse.model_validate(lp)


@router.get("", response_model=LessonPlanListResponse)
async def list_lesson_plans_endpoint(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanListResponse:
    items, total = await list_lesson_plans(db, client_id=current_client.id, limit=limit, offset=offset)
    return LessonPlanListResponse(
        items=[LessonPlanResponse.model_validate(lp) for lp in items],
        total=total,
    )


@router.get("/{lp_id}", response_model=LessonPlanResponse)
async def get_lesson_plan_endpoint(
    lp_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    lp = await get_lesson_plan(db, client_id=current_client.id, lp_id=lp_id)
    if lp is None:
        raise HTTPException(status_code=404, detail="Lesson plan not found")
    return LessonPlanResponse.model_validate(lp)
