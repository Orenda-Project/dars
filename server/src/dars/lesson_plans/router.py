import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.database import get_db
from dars.deps import get_current_client, get_effective_teacher, require_teacher
from dars.lesson_plans.schemas import (
    LessonPlanCreateRequest,
    LessonPlanEditRequest,
    LessonPlanListResponse,
    LessonPlanResponse,
    LessonPlanReviewRequest,
    LessonPlanReviewResponse,
)
from dars.teachers.models import Teacher
from dars.lesson_plans.service import (
    edit_lesson_plan,
    generate_lesson_plan_task,
    get_lesson_plan,
    list_lesson_plans,
    queue_lesson_plan,
    review_lesson_plan,
)

router = APIRouter(prefix="/api/v1/lesson-plans", tags=["lesson-plans"])


@router.post("/review", response_model=LessonPlanReviewResponse)
async def review_lesson_plan_endpoint(
    body: LessonPlanReviewRequest,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanReviewResponse:
    try:
        review = await review_lesson_plan(db, client_id=current_client.id, request=body)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return LessonPlanReviewResponse(review=review)


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=LessonPlanResponse)
async def create_lesson_plan_endpoint(
    body: LessonPlanCreateRequest,
    background_tasks: BackgroundTasks,
    teacher: Teacher = Depends(get_effective_teacher),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    lp = await queue_lesson_plan(db, client_id=current_client.id, teacher_id=teacher.id, request=body)
    background_tasks.add_task(
        generate_lesson_plan_task,
        lp_id=lp.id,
        client_id=current_client.id,
        webhook_url=current_client.webhook_url,
        request=body,
    )
    return LessonPlanResponse.model_validate(lp)


@router.get("", response_model=LessonPlanListResponse)
async def list_lesson_plans_endpoint(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    teacher_id: uuid.UUID | None = Query(None),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanListResponse:
    items, total = await list_lesson_plans(
        db,
        client_id=current_client.id,
        limit=limit,
        offset=offset,
        teacher_id=teacher_id,
    )
    return LessonPlanListResponse(
        items=[LessonPlanResponse.model_validate(lp) for lp in items],
        total=total,
    )


@router.patch("/{lp_id}", response_model=LessonPlanResponse)
async def edit_lesson_plan_endpoint(
    lp_id: uuid.UUID,
    body: LessonPlanEditRequest,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    try:
        lp = await edit_lesson_plan(db, client_id=current_client.id, lp_id=lp_id, request=body)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if lp is None:
        raise HTTPException(status_code=404, detail="Lesson plan not found")
    return LessonPlanResponse.model_validate(lp)


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
