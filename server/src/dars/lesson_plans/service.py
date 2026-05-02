import logging
import uuid

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dars.config import settings
from dars.lesson_plans.models import LessonPlan
from dars.lesson_plans.schemas import LessonPlanCreateRequest
from dars.mapping import canonical_grade, canonical_subject
from dars.webhooks.service import deliver_webhook

logger = logging.getLogger(__name__)


async def queue_lesson_plan(
    db: AsyncSession,
    client_id: uuid.UUID,
    request: LessonPlanCreateRequest,
) -> LessonPlan:
    """Create a PENDING lesson plan record and return it. Background task fires separately."""
    logger.info(
        "queue_lesson_plan: client_id=%s curriculum=%s grade=%s subject=%s topic=%s",
        client_id, request.curriculum, request.grade, request.subject, request.topic,
    )
    lp = LessonPlan(
        client_id=client_id,
        webhook_url=request.webhook_url,
        curriculum=request.curriculum,
        grade=str(request.grade),
        subject=request.subject,
        topic=request.topic,
        page_number=request.page_number or None,
        class_strength=request.class_strength,
        external_ref=request.external_ref,
        status="PENDING",
    )
    db.add(lp)
    await db.commit()
    await db.refresh(lp)
    logger.info("queue_lesson_plan: queued lp_id=%s client_id=%s", lp.id, client_id)
    return lp


async def get_lesson_plan(
    db: AsyncSession,
    lp_id: uuid.UUID,
    client_id: uuid.UUID | None = None,
) -> LessonPlan | None:
    q = select(LessonPlan).where(LessonPlan.id == lp_id)
    if client_id is not None:
        q = q.where(LessonPlan.client_id == client_id)
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def list_lesson_plans(
    db: AsyncSession,
    client_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[LessonPlan], int]:
    """Return (items, total) for paginated lesson plan list, always filtered by client_id."""
    count_result = await db.execute(
        select(func.count()).select_from(LessonPlan).where(LessonPlan.client_id == client_id)
    )
    total = count_result.scalar_one()

    items_result = await db.execute(
        select(LessonPlan)
        .where(LessonPlan.client_id == client_id)
        .order_by(LessonPlan.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(items_result.scalars().all())
    return items, total


async def generate_lesson_plan_task(
    lp_id: uuid.UUID,
    client_id: uuid.UUID,
    request: LessonPlanCreateRequest,
) -> None:
    """
    Background task: call LP Assistant, update LessonPlan record, fire webhook.
    Uses its own DB session (background tasks run outside request context).
    """
    logger.info("generate_lesson_plan_task: lp_id=%s client_id=%s", lp_id, client_id)
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        lp = await db.get(LessonPlan, lp_id)
        if lp is None:
            logger.error("generate_lesson_plan_task: LP %s not found", lp_id)
            await engine.dispose()
            return

        # Build LP Assistant payload — ensure canonical values before sending upstream
        payload = {
            "curriculum": request.curriculum,
            "grade": canonical_grade(request.grade),
            "subject": canonical_subject(request.subject),
            "page_number": request.page_number or "",
            "class_strength": request.class_strength or 30,
            "exercise_page_number": request.exercise_page_number,
            "custom_prompt": request.custom_prompt,
            "generate_bilingual": request.generate_bilingual,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as http:
                response = await http.post(
                    f"{settings.lp_assistant_url}/api/generate-lp",
                    json=payload,
                    headers={"api-key": settings.lp_assistant_api_key},
                )
            if response.is_error:
                logger.error("LP assistant error for lp=%s: HTTP %s — %s", lp_id, response.status_code, response.text)
            response.raise_for_status()
            data = response.json()

            lp.content = data.get("lesson_plan", "")
            lp.content_bilingual = data.get("lesson_plan_bilingual")
            lp.tags = data.get("tags") or {}
            lp.metadata_ = data.get("metadata") or {}
            lp.status = "READY"
            event = "lesson_plan.ready"

        except Exception as exc:
            logger.error("LP generation failed for lp=%s: %s", lp_id, exc, exc_info=True)
            lp.status = "ERROR"
            event = "lesson_plan.error"

        await db.commit()
        await db.refresh(lp)
        logger.info("LP %s marked %s", lp_id, lp.status)

        # Fire webhook if URL is configured on the LP record
        if lp.webhook_url:
            webhook_payload = {
                "event": event,
                "lesson_plan_id": str(lp_id),
                "status": lp.status,
            }
            logger.info(
                "generate_lesson_plan_task: delivering webhook event=%s lp_id=%s client_id=%s",
                event, lp_id, client_id,
            )
            try:
                await deliver_webhook(
                    db=db,
                    client_id=client_id,
                    lesson_plan_id=lp_id,
                    webhook_url=lp.webhook_url,
                    event=event,
                    payload=webhook_payload,
                )
            except Exception as exc:
                logger.error("Webhook delivery failed for lp=%s: %s", lp_id, exc, exc_info=True)

    await engine.dispose()
