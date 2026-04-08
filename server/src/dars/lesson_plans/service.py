import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.config import settings
from dars.lesson_plans.models import LessonPlan
from dars.lesson_plans.schemas import LessonPlanCreateRequest

logger = logging.getLogger(__name__)


async def _call_lp_assistant(request: LessonPlanCreateRequest) -> dict:
    payload = {
        "curriculum": request.curriculum,
        "grade": int(request.grade) if request.grade.isdigit() else request.grade,
        "subject": request.subject,
        "page_number": request.page_number,
        "class_strength": request.class_strength or 30,
        "exercise_page_number": request.exercise_page_number,
        "custom_prompt": request.custom_prompt,
        "generate_bilingual": request.generate_bilingual,
    }
    async with httpx.AsyncClient(timeout=300.0) as http:
        response = await http.post(
            f"{settings.lp_assistant_url}/api/generate-lp",
            json=payload,
            headers={"api-key": settings.lp_assistant_api_key},
        )
        logger.info(
            "LP assistant HTTP response: status=%s url=%s",
            response.status_code,
            response.url,
        )
        if response.is_error:
            logger.error(
                "LP assistant error response body: %s", response.text
            )
        else:
            logger.debug("LP assistant response body (first 500 chars): %.500s", response.text)
        response.raise_for_status()
        return response.json()


async def queue_lesson_plan(
    db: AsyncSession,
    client_id: uuid.UUID,
    request: LessonPlanCreateRequest,
) -> LessonPlan:
    """Create a PENDING lesson plan record. Caller must schedule generate_lesson_plan_task as a background task."""
    lp = LessonPlan(
        client_id=client_id,
        external_ref=request.external_ref,
        grade=request.grade,
        subject=request.subject,
        topic=request.topic,
        page_number=request.page_number,
        class_strength=request.class_strength,
        status="PENDING",
    )
    db.add(lp)
    await db.commit()
    await db.refresh(lp)
    return lp


async def generate_lesson_plan_task(
    lp_id: uuid.UUID,
    client_id: uuid.UUID,
    webhook_url: str | None,
    request: LessonPlanCreateRequest,
) -> None:
    """Background task: opens its own DB session, generates LP, fires webhook."""
    from dars.database import AsyncSessionLocal

    event: str = "lesson_plan.error"

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(LessonPlan).where(
                LessonPlan.id == lp_id, LessonPlan.client_id == client_id
            )
        )
        lp = result.scalar_one_or_none()
        if lp is None:
            logger.error("generate_lesson_plan_task: LP not found lp_id=%s", lp_id)
            return

        try:
            logger.info(
                "Calling LP assistant for lp_id=%s grade=%s subject=%s page=%s",
                lp.id,
                request.grade,
                request.subject,
                request.page_number,
            )
            result_data = await _call_lp_assistant(request)
            logger.info(
                "LP assistant responded for lp_id=%s status=%s",
                lp.id,
                result_data.get("status"),
            )
            lp.content = result_data.get("lesson_plan")
            lp.content_bilingual = result_data.get("lesson_plan_bilingual")
            lp.tags = result_data.get("tags") or {}
            lp.metadata_ = result_data.get("metadata") or {}
            lp.status = "READY"
            event = "lesson_plan.ready"
        except httpx.HTTPStatusError:
            # response body already logged inside _call_lp_assistant
            lp.status = "ERROR"
        except Exception as e:
            logger.error("LP assistant failed for lp_id=%s: %s", lp.id, e)
            lp.status = "ERROR"

        lp.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(lp)

        if webhook_url:
            from dars.lesson_plans.schemas import LessonPlanResponse
            from dars.webhooks.service import deliver_webhook

            payload = {
                "event": event,
                "lesson_plan": LessonPlanResponse.model_validate(lp).model_dump(
                    mode="json"
                ),
            }
            await deliver_webhook(
                db=db,
                client_id=client_id,
                lesson_plan_id=lp.id,
                webhook_url=webhook_url,
                event=event,
                payload=payload,
            )


async def list_lesson_plans(
    db: AsyncSession,
    client_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[LessonPlan], int]:
    count_result = await db.execute(
        select(func.count())
        .select_from(LessonPlan)
        .where(LessonPlan.client_id == client_id)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(LessonPlan)
        .where(LessonPlan.client_id == client_id)
        .order_by(LessonPlan.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list(result.scalars().all())
    return items, total


async def get_lesson_plan(
    db: AsyncSession,
    client_id: uuid.UUID,
    lp_id: uuid.UUID,
) -> LessonPlan | None:
    result = await db.execute(
        select(LessonPlan).where(
            LessonPlan.id == lp_id,
            LessonPlan.client_id == client_id,
        )
    )
    return result.scalar_one_or_none()
