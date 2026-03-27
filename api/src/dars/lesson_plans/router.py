import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.database import get_db
from dars.deps import get_current_client
from dars.lesson_plans.schemas import (
    LessonPlanCreateRequest,
    LessonPlanListResponse,
    LessonPlanResponse,
)
from dars.lesson_plans.service import create_lesson_plan, get_lesson_plan, list_lesson_plans

router = APIRouter(prefix="/api/v1/lesson-plans", tags=["lesson-plans"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=LessonPlanResponse)
async def create_lesson_plan_endpoint(
    body: LessonPlanCreateRequest,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanResponse:
    lp = await create_lesson_plan(db, client_id=current_client.id, request=body)
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
