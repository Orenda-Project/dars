import logging
import uuid

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dars.config import settings
from dars.custom_lesson_plans.models import CustomLessonPlan
from dars.custom_lesson_plans.schemas import CustomLessonPlanCreateRequest
from dars.mapping import canonical_grade, canonical_subject

logger = logging.getLogger(__name__)


async def queue_custom_lesson_plan(
    db: AsyncSession,
    client_id: uuid.UUID,
    curriculum: str,
    request: CustomLessonPlanCreateRequest,
) -> CustomLessonPlan:
    """Create a PENDING custom lesson plan record and return it. Background task fires separately."""
    logger.info(
        "queue_custom_lesson_plan: client_id=%s curriculum=%s grade=%s subject=%s topic=%s",
        client_id, curriculum, request.grade, request.subject, request.topic,
    )
    lp = CustomLessonPlan(
        client_id=client_id,
        curriculum=curriculum,
        grade=str(request.grade),
        subject=request.subject,
        topic=request.topic,
        page_number=request.page_number or None,
        external_id=request.external_id,
        status="PENDING",
    )
    db.add(lp)
    await db.commit()
    await db.refresh(lp)
    logger.info(
        "queue_custom_lesson_plan: queued lp_id=%s client_id=%s",
        lp.id, client_id,
    )
    return lp


async def get_custom_lesson_plan(
    db: AsyncSession,
    client_id: uuid.UUID,
    lp_id: uuid.UUID,
) -> CustomLessonPlan | None:
    """Fetch a single custom lesson plan, always filtering by client_id."""
    result = await db.execute(
        select(CustomLessonPlan).where(
            CustomLessonPlan.id == lp_id,
            CustomLessonPlan.client_id == client_id,
        )
    )
    return result.scalar_one_or_none()


async def list_custom_lesson_plans(
    db: AsyncSession,
    client_id: uuid.UUID,
    external_id: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[CustomLessonPlan], int]:
    """Return (items, total) for paginated custom lesson plan list, filtered by client_id."""
    base_filter = [CustomLessonPlan.client_id == client_id]
    if external_id is not None:
        base_filter.append(CustomLessonPlan.external_id == external_id)

    count_result = await db.execute(
        select(func.count()).select_from(CustomLessonPlan).where(*base_filter)
    )
    total = count_result.scalar_one()

    items_result = await db.execute(
        select(CustomLessonPlan)
        .where(*base_filter)
        .order_by(CustomLessonPlan.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(items_result.scalars().all())
    return items, total


async def generate_custom_lesson_plan_task(
    lp_id: uuid.UUID,
    client_id: uuid.UUID,
    curriculum: str,
    request: CustomLessonPlanCreateRequest,
) -> None:
    """
    Background task: call LP Assistant, update CustomLessonPlan record.
    Uses its own DB session (background tasks run outside request context).
    """
    logger.info(
        "generate_custom_lesson_plan_task: lp_id=%s client_id=%s",
        lp_id, client_id,
    )
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        lp = await db.get(CustomLessonPlan, lp_id)
        if lp is None:
            logger.error(
                "generate_custom_lesson_plan_task: CustomLessonPlan %s not found", lp_id
            )
            await engine.dispose()
            return

        payload = {
            "curriculum": curriculum,
            "grade": canonical_grade(request.grade),
            "subject": canonical_subject(request.subject),
            "page_number": request.page_number or "",
            "class_strength": request.class_strength or 30,
            "generate_bilingual": request.generate_bilingual,
        }
        if request.topic:
            payload["topic"] = request.topic

        try:
            async with httpx.AsyncClient(timeout=120.0) as http:
                response = await http.post(
                    f"{settings.lp_assistant_url}/api/generate-lp",
                    json=payload,
                    headers={"api-key": settings.lp_assistant_api_key},
                )
            if response.is_error:
                logger.error(
                    "LP assistant error for custom_lp=%s: HTTP %s — %s",
                    lp_id, response.status_code, response.text,
                )
            response.raise_for_status()
            data = response.json()

            lp.content = data.get("lesson_plan", "")
            lp.content_bilingual = data.get("lesson_plan_bilingual")
            lp.tags = data.get("tags") or {}
            lp.metadata_ = data.get("metadata") or {}
            lp.status = "READY"

        except Exception as exc:
            logger.error(
                "Custom LP generation failed for lp=%s: %s", lp_id, exc, exc_info=True
            )
            lp.status = "ERROR"

        await db.commit()
        await db.refresh(lp)
        logger.info("CustomLessonPlan %s marked %s", lp_id, lp.status)

    await engine.dispose()
