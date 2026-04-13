import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.teachers.models import Teacher
from dars.teachers.schemas import TeacherRegisterRequest, TeacherUpdateRequest


async def register_teacher(
    db: AsyncSession, client_id: uuid.UUID, request: TeacherRegisterRequest
) -> Teacher:
    existing = await db.execute(
        select(Teacher).where(
            Teacher.client_id == client_id,
            Teacher.email == request.email,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"A teacher with email '{request.email}' already exists for this client.")

    teacher = Teacher(
        client_id=client_id,
        name=request.name,
        email=request.email,
        phone=request.phone,
        school=request.school,
    )
    db.add(teacher)
    await db.commit()
    await db.refresh(teacher)
    return teacher


async def get_teacher(
    db: AsyncSession, client_id: uuid.UUID, teacher_id: uuid.UUID
) -> Teacher | None:
    result = await db.execute(
        select(Teacher).where(
            Teacher.id == teacher_id,
            Teacher.client_id == client_id,
        )
    )
    return result.scalar_one_or_none()


async def list_teachers(
    db: AsyncSession,
    client_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
    search: str | None = None,
) -> tuple[list[Teacher], int]:
    base_filter = Teacher.client_id == client_id
    if search:
        pattern = f"%{search}%"
        search_filter = Teacher.name.ilike(pattern) | Teacher.email.ilike(pattern)
        where_clause = base_filter & search_filter
    else:
        where_clause = base_filter

    count_result = await db.execute(
        select(func.count()).select_from(Teacher).where(where_clause)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Teacher)
        .where(where_clause)
        .order_by(Teacher.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def update_teacher(
    db: AsyncSession,
    client_id: uuid.UUID,
    teacher_id: uuid.UUID,
    request: TeacherUpdateRequest,
) -> Teacher | None:
    teacher = await get_teacher(db, client_id=client_id, teacher_id=teacher_id)
    if teacher is None:
        return None

    if request.name is not None:
        teacher.name = request.name
    if request.phone is not None:
        teacher.phone = request.phone
    if request.school is not None:
        teacher.school = request.school
    if request.is_active is not None:
        teacher.is_active = request.is_active

    await db.commit()
    await db.refresh(teacher)
    return teacher
