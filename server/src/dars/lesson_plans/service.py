import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.config import settings
from dars.lesson_plans.models import LessonPlan
from dars.lesson_plans.schemas import LessonPlanCreateRequest, LessonPlanEditRequest, LessonPlanReviewRequest

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


_SUBJECT_MAP: dict[str, str] = {
    "Eng": "English",
    "Urdu": "Urdu",
    "Maths": "Maths",
    "Science": "Science",
}


async def _call_lp_reviewer(lesson_plan_html: str, subject: str, grade: int) -> dict:
    mapped_subject = _SUBJECT_MAP.get(subject, subject)
    payload = {
        "lesson_plan_html": lesson_plan_html,
        "subject": mapped_subject,
        "grade": grade,
    }
    async with httpx.AsyncClient(timeout=300.0) as http:
        response = await http.post(
            f"{settings.lp_assistant_url}/api/review-lp",
            json=payload,
            headers={"api-key": settings.lp_assistant_api_key},
        )
        logger.info(
            "LP reviewer HTTP response: status=%s url=%s",
            response.status_code,
            response.url,
        )
        if response.is_error:
            logger.error("LP reviewer error response body: %s", response.text)
        else:
            logger.debug("LP reviewer response body (first 500 chars): %.500s", response.text)
        response.raise_for_status()
        return response.json()


async def review_lesson_plan(
    db: AsyncSession,
    client_id: uuid.UUID,
    request: LessonPlanReviewRequest,
) -> dict:
    """Review a lesson plan. If lesson_plan_id is given, fetch content, call reviewer, store result.
    If lesson_plan_html is given, call reviewer and return without storing."""
    if request.lesson_plan_id is not None:
        lp = await get_lesson_plan(db, client_id=client_id, lp_id=request.lesson_plan_id)
        if lp is None:
            raise LookupError("Lesson plan not found")
        if not lp.content:
            raise ValueError("Lesson plan has no content to review.")
        html = lp.content
        grade = int(lp.grade) if lp.grade.isdigit() else lp.grade  # type: ignore[union-attr]
        review = await _call_lp_reviewer(html, subject=lp.subject, grade=grade)  # type: ignore[arg-type]
        lp.review = review
        lp.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return review
    else:
        # raw HTML path — no DB interaction
        return await _call_lp_reviewer(
            request.lesson_plan_html,  # type: ignore[arg-type]
            subject=request.subject,
            grade=request.grade,
        )


async def queue_lesson_plan(
    db: AsyncSession,
    client_id: uuid.UUID,
    teacher_id: uuid.UUID,
    request: LessonPlanCreateRequest,
) -> LessonPlan:
    """Create a PENDING lesson plan record. Caller must schedule generate_lesson_plan_task as a background task."""
    lp = LessonPlan(
        client_id=client_id,
        teacher_id=teacher_id,
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


async def edit_lesson_plan(
    db: AsyncSession,
    client_id: uuid.UUID,
    lp_id: uuid.UUID,
    request: LessonPlanEditRequest,
) -> LessonPlan | None:
    """Call LP Assistant /api/edit-lp, save history, and persist updated content atomically.

    History row and content update are committed together — if the HTTP call or
    commit fails, neither the history nor the LP content changes.
    Returns None if not found.
    """
    from dars.lesson_plans.edit_models import LessonPlanEdit

    lp = await get_lesson_plan(db, client_id=client_id, lp_id=lp_id)
    if lp is None:
        return None

    if lp.status != "READY":
        raise ValueError(f"Cannot edit a lesson plan with status '{lp.status}'. Only READY plans can be edited.")

    if not lp.content:
        raise ValueError("Lesson plan has no content to edit.")

    # Stage history row before HTTP call — committed atomically with content update below.
    # If the HTTP call raises, the session is never committed and this row is discarded.
    edit_record = LessonPlanEdit(
        client_id=client_id,
        lp_id=lp_id,
        edit_prompt=request.edit_prompt,
        content_before=lp.content,
        content_bilingual_before=lp.content_bilingual,
    )
    db.add(edit_record)

    payload = {
        "existing_lp_html": lp.content,
        "edit_prompt": request.edit_prompt,
        "grade": int(lp.grade) if lp.grade.isdigit() else lp.grade,
        "subject": lp.subject,
        "page_number": lp.page_number or "",
        "class_strength": lp.class_strength or 30,
        "curriculum": "ICT",
    }

    async with httpx.AsyncClient(timeout=300.0) as http:
        response = await http.post(
            f"{settings.lp_assistant_url}/api/edit-lp",
            json=payload,
            headers={"api-key": settings.lp_assistant_api_key},
        )
        logger.info(
            "LP assistant edit HTTP response: status=%s url=%s",
            response.status_code,
            response.url,
        )
        if response.is_error:
            logger.error("LP assistant edit error response body: %s", response.text)
        response.raise_for_status()
        result = response.json()

    lp.content = result.get("edited_lesson_plan_english") or lp.content
    lp.content_bilingual = result.get("edited_lesson_plan_bilingual") or lp.content_bilingual
    lp.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(lp)
    return lp


async def list_lesson_plans(
    db: AsyncSession,
    client_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
    teacher_id: uuid.UUID | None = None,
) -> tuple[list[LessonPlan], int]:
    base_where = [LessonPlan.client_id == client_id]
    if teacher_id is not None:
        base_where.append(LessonPlan.teacher_id == teacher_id)

    count_result = await db.execute(
        select(func.count())
        .select_from(LessonPlan)
        .where(*base_where)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(LessonPlan)
        .where(*base_where)
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
