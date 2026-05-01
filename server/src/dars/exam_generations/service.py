import logging
import uuid

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dars.config import settings
from dars.exam_generations.models import ExamGeneration
from dars.exam_generations.schemas import ExamGenerationCreateRequest
from dars.mapping import canonical_grade, canonical_subject

logger = logging.getLogger(__name__)


async def queue_exam_generation(
    db: AsyncSession,
    client_id: uuid.UUID,
    request: ExamGenerationCreateRequest,
) -> ExamGeneration:
    """Create a PENDING exam generation record and return it. Background task fires separately."""
    eg = ExamGeneration(
        client_id=client_id,
        webhook_url=request.webhook_url,
        curriculum=request.curriculum,
        grade=request.grade,
        subject=request.subject,
        page_ranges=request.page_ranges,
        generation_type=request.generation_type,
        external_ref=request.external_ref,
        status="PENDING",
    )
    db.add(eg)
    await db.commit()
    await db.refresh(eg)
    return eg


async def get_exam_generation(
    db: AsyncSession,
    client_id: uuid.UUID,
    eg_id: uuid.UUID,
) -> ExamGeneration | None:
    """Fetch a single exam generation, always filtering by client_id."""
    result = await db.execute(
        select(ExamGeneration).where(
            ExamGeneration.id == eg_id,
            ExamGeneration.client_id == client_id,
        )
    )
    return result.scalar_one_or_none()


async def list_exam_generations(
    db: AsyncSession,
    client_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[ExamGeneration], int]:
    """Return (items, total) for paginated exam generation list, always filtered by client_id."""
    count_result = await db.execute(
        select(func.count()).select_from(ExamGeneration).where(ExamGeneration.client_id == client_id)
    )
    total = count_result.scalar_one()

    items_result = await db.execute(
        select(ExamGeneration)
        .where(ExamGeneration.client_id == client_id)
        .order_by(ExamGeneration.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(items_result.scalars().all())
    return items, total


async def generate_exam_task(
    eg_id: uuid.UUID,
    client_id: uuid.UUID,
    request: ExamGenerationCreateRequest,
) -> None:
    """
    Background task: call EG Assistant, update ExamGeneration record, fire webhook.
    Uses its own DB session (background tasks run outside request context).
    """
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        eg = await db.get(ExamGeneration, eg_id)
        if eg is None:
            logger.error("generate_exam_task: ExamGeneration %s not found", eg_id)
            await engine.dispose()
            return

        # Build EG Assistant payload — ensure canonical values before sending upstream
        payload: dict = {
            "generation_type": request.generation_type,
            "curriculum": request.curriculum,
            "grade": canonical_grade(request.grade),
            "subject": canonical_subject(request.subject),
            "page_ranges": request.page_ranges,
            "question_types": request.question_types,
            "image_generation_enabled": request.image_generation_enabled,
            "include_answer_key": request.include_answer_key,
            "enable_review": request.enable_review,
        }

        # Include optional fields only if set
        if request.custom_system_prompt is not None:
            payload["custom_system_prompt"] = request.custom_system_prompt
        if request.seen_categories is not None:
            payload["seen_categories"] = request.seen_categories
        if request.unseen_categories is not None:
            payload["unseen_categories"] = request.unseen_categories
        if request.unseen_objective_types is not None:
            payload["unseen_objective_types"] = request.unseen_objective_types
        if request.unseen_subjective_types is not None:
            payload["unseen_subjective_types"] = request.unseen_subjective_types
        if request.unseen_objective_counts is not None:
            payload["unseen_objective_counts"] = request.unseen_objective_counts
        if request.unseen_subjective_counts is not None:
            payload["unseen_subjective_counts"] = request.unseen_subjective_counts
        if request.long_question_sub_types is not None:
            payload["long_question_sub_types"] = request.long_question_sub_types

        try:
            async with httpx.AsyncClient(timeout=120.0) as http:
                response = await http.post(
                    f"{settings.eg_assistant_url}/api/generate-exam",
                    json=payload,
                    headers={"api-key": settings.eg_assistant_api_key},
                )
            if response.is_error:
                logger.error(
                    "EG assistant error for eg=%s: HTTP %s — %s",
                    eg_id, response.status_code, response.text,
                )
            response.raise_for_status()
            data = response.json()

            eg.result = data
            eg.status = "READY"
            event = "exam_generation.ready"

        except Exception as exc:
            logger.error("EG generation failed for eg=%s: %s", eg_id, exc)
            eg.error_detail = str(exc)
            eg.status = "ERROR"
            event = "exam_generation.error"

        await db.commit()
        await db.refresh(eg)
        logger.info("ExamGeneration %s marked %s", eg_id, eg.status)

        # Fire webhook if URL is configured on the record
        if eg.webhook_url:
            webhook_payload = {
                "event": event,
                "exam_generation_id": str(eg_id),
                "status": eg.status,
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as http:
                    await http.post(eg.webhook_url, json=webhook_payload)
            except Exception as exc:
                logger.error("Webhook delivery failed for eg=%s: %s", eg_id, exc)

    await engine.dispose()
