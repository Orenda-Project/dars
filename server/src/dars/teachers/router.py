import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.database import get_db
from dars.deps import get_current_client
from dars.teachers.schemas import (
    TeacherListResponse,
    TeacherRegisterRequest,
    TeacherResponse,
    TeacherUpdateRequest,
)
from dars.teachers.service import (
    get_teacher,
    list_teachers,
    register_teacher_and_commit,
    update_teacher,
)

router = APIRouter(prefix="/api/v1/teachers", tags=["teachers"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TeacherResponse)
async def register_teacher_endpoint(
    body: TeacherRegisterRequest,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> TeacherResponse:
    try:
        teacher = await register_teacher_and_commit(db, client_id=current_client.id, request=body)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return TeacherResponse.model_validate(teacher)


@router.get("", response_model=TeacherListResponse)
async def list_teachers_endpoint(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, max_length=200),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> TeacherListResponse:
    items, total = await list_teachers(
        db, client_id=current_client.id, limit=limit, offset=offset, search=search or None
    )
    return TeacherListResponse(
        items=[TeacherResponse.model_validate(t) for t in items],
        total=total,
    )


@router.get("/{teacher_id}", response_model=TeacherResponse)
async def get_teacher_endpoint(
    teacher_id: uuid.UUID,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> TeacherResponse:
    teacher = await get_teacher(db, client_id=current_client.id, teacher_id=teacher_id)
    if teacher is None:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return TeacherResponse.model_validate(teacher)


@router.patch("/{teacher_id}", response_model=TeacherResponse)
async def update_teacher_endpoint(
    teacher_id: uuid.UUID,
    body: TeacherUpdateRequest,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> TeacherResponse:
    teacher = await update_teacher(
        db, client_id=current_client.id, teacher_id=teacher_id, request=body
    )
    if teacher is None:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return TeacherResponse.model_validate(teacher)
