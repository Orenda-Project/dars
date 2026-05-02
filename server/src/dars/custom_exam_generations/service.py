import logging
import uuid

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dars.config import settings
from dars.custom_exam_generations.models import CustomExamGeneration
from dars.custom_exam_generations.schemas import CustomExamGenerationCreateRequest
from dars.mapping import canonical_grade, canonical_subject

logger = logging.getLogger(__name__)


async def queue_custom_exam_generation(
    db: AsyncSession,
    client_id: uuid.UUID,
    curriculum: str,
    request: CustomExamGenerationCreateRequest,
) -> CustomExamGeneration:
    """Create a PENDING custom exam generation record and return it. Background task fires separately."""
    logger.info(
        "queue_custom_exam_generation: client_id=%s curriculum=%s grade=%s subject=%s type=%s",
        client_id, curriculum, request.grade, request.subject, request.generation_type,
    )
    eg = CustomExamGeneration(
        client_id=client_id,
        curriculum=curriculum,
        grade=request.grade,
        subject=request.subject,
        page_ranges=request.page_ranges,
        generation_type=request.generation_type,
        external_id=request.external_id,
        status="PENDING",
    )
    db.add(eg)
    await db.commit()
    await db.refresh(eg)
    logger.info(
        "queue_custom_exam_generation: queued eg_id=%s client_id=%s",
        eg.id, client_id,
    )
    return eg


async def get_custom_exam_generation(
    db: AsyncSession,
    client_id: uuid.UUID,
    eg_id: uuid.UUID,
) -> CustomExamGeneration | None:
    """Fetch a single custom exam generation, always filtering by client_id."""
    result = await db.execute(
        select(CustomExamGeneration).where(
            CustomExamGeneration.id == eg_id,
            CustomExamGeneration.client_id == client_id,
        )
    )
    return result.scalar_one_or_none()


async def list_custom_exam_generations(
    db: AsyncSession,
    client_id: uuid.UUID,
    external_id: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[CustomExamGeneration], int]:
    """Return (items, total) for paginated custom exam generation list, filtered by client_id."""
    base_filter = [CustomExamGeneration.client_id == client_id]
    if external_id is not None:
        base_filter.append(CustomExamGeneration.external_id == external_id)

    count_result = await db.execute(
        select(func.count()).select_from(CustomExamGeneration).where(*base_filter)
    )
    total = count_result.scalar_one()

    items_result = await db.execute(
        select(CustomExamGeneration)
        .where(*base_filter)
        .order_by(CustomExamGeneration.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(items_result.scalars().all())
    return items, total


async def generate_custom_exam_task(
    eg_id: uuid.UUID,
    client_id: uuid.UUID,
    curriculum: str,
    request: CustomExamGenerationCreateRequest,
) -> None:
    """
    Background task: call EG Assistant, update CustomExamGeneration record.
    Uses its own DB session (background tasks run outside request context).
    """
    logger.info(
        "generate_custom_exam_task: eg_id=%s client_id=%s",
        eg_id, client_id,
    )
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        eg = await db.get(CustomExamGeneration, eg_id)
        if eg is None:
            logger.error(
                "generate_custom_exam_task: CustomExamGeneration %s not found", eg_id
            )
            await engine.dispose()
            return

        payload: dict = {
            "generation_type": request.generation_type,
            "curriculum": curriculum,
            "grade": canonical_grade(request.grade),
            "subject": canonical_subject(request.subject),
            "page_ranges": request.page_ranges,
            "include_answer_key": request.include_answer_key,
        }
        if request.question_types is not None:
            payload["question_types"] = request.question_types
        if request.seen_categories is not None:
            payload["seen_categories"] = request.seen_categories
        if request.unseen_categories is not None:
            payload["unseen_categories"] = request.unseen_categories

        try:
            async with httpx.AsyncClient(timeout=120.0) as http:
                response = await http.post(
                    f"{settings.eg_assistant_url}/api/generate-exam",
                    json=payload,
                    headers={"api-key": settings.eg_assistant_api_key},
                )
            if response.is_error:
                logger.error(
                    "EG assistant error for custom_eg=%s: HTTP %s — %s",
                    eg_id, response.status_code, response.text,
                )
            response.raise_for_status()
            data = response.json()

            eg.result = data
            eg.status = "READY"

        except Exception as exc:
            logger.error(
                "Custom EG generation failed for eg=%s: %s", eg_id, exc, exc_info=True
            )
            eg.error_detail = str(exc)
            eg.status = "ERROR"

        await db.commit()
        await db.refresh(eg)
        logger.info("CustomExamGeneration %s marked %s", eg_id, eg.status)

    await engine.dispose()
