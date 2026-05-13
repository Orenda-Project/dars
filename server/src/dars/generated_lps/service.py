import logging
import uuid

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dars.config import settings
from dars.generated_lps.models import GeneratedLP
from dars.generated_lps.schemas import GeneratedLPCreate
from dars.mapping import canonical_grade, canonical_subject

logger = logging.getLogger(__name__)


async def create_generated_lp(
    db: AsyncSession,
    client_id: uuid.UUID,
    data: GeneratedLPCreate,
    curriculum: str,
) -> GeneratedLP:
    """Create a PENDING generated LP record and return it. Background task fires separately."""
    logger.info(
        "create_generated_lp: client_id=%s curriculum=%s grade=%s subject=%s topic=%s",
        client_id, curriculum, data.grade, data.subject, data.topic,
    )
    lp = GeneratedLP(
        client_id=client_id,
        curriculum=curriculum,
        grade=str(data.grade),
        subject=data.subject,
        topic=data.topic,
        page_number=data.page_number or None,
        class_strength=data.class_strength,
        lp_type=data.lp_type,
        external_id=data.external_id,
        status="PENDING",
    )
    db.add(lp)
    await db.commit()
    await db.refresh(lp)
    logger.info("create_generated_lp: queued lp_id=%s client_id=%s", lp.id, client_id)
    return lp


async def get_generated_lp(
    db: AsyncSession,
    lp_id: uuid.UUID,
    client_id: uuid.UUID,
) -> GeneratedLP | None:
    """Fetch a single generated LP, always filtering by client_id."""
    result = await db.execute(
        select(GeneratedLP).where(
            GeneratedLP.id == lp_id,
            GeneratedLP.client_id == client_id,
        )
    )
    return result.scalar_one_or_none()


async def list_generated_lps(
    db: AsyncSession,
    client_id: uuid.UUID,
    external_id: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[GeneratedLP], int]:
    """Return (items, total) for paginated generated LP list, filtered by client_id."""
    base_filter = [GeneratedLP.client_id == client_id]
    if external_id is not None:
        base_filter.append(GeneratedLP.external_id == external_id)

    count_result = await db.execute(
        select(func.count()).select_from(GeneratedLP).where(*base_filter)
    )
    total = count_result.scalar_one()

    items_result = await db.execute(
        select(GeneratedLP)
        .where(*base_filter)
        .order_by(GeneratedLP.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = list(items_result.scalars().all())
    return items, total


async def update_lp_status(
    db: AsyncSession,
    lp_id: uuid.UUID,
    status: str,
    content: str | None = None,
    content_bilingual: str | None = None,
    tags: dict | None = None,
    metadata: dict | None = None,
    error_message: str | None = None,
) -> None:
    """Update status and optional content fields on a GeneratedLP."""
    lp = await db.get(GeneratedLP, lp_id)
    if lp is None:
        logger.error("update_lp_status: GeneratedLP %s not found", lp_id)
        return
    lp.status = status
    if content is not None:
        lp.content = content
    if content_bilingual is not None:
        lp.content_bilingual = content_bilingual
    if tags is not None:
        lp.tags = tags
    if metadata is not None:
        lp.metadata_ = metadata
    if error_message is not None:
        lp.error_message = error_message
    await db.commit()


async def generate_lp_task(
    lp_id: uuid.UUID,
    client_id: uuid.UUID,
    curriculum: str,
    request: GeneratedLPCreate,
) -> None:
    """
    Background task: call LP Assistant, update GeneratedLP record.
    Uses its own DB session (background tasks run outside request context).
    """
    logger.info("generate_lp_task: lp_id=%s client_id=%s", lp_id, client_id)
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        lp = await db.get(GeneratedLP, lp_id)
        if lp is None:
            logger.error("generate_lp_task: GeneratedLP %s not found", lp_id)
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
                    "LP assistant error for lp=%s: HTTP %s — %s",
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
            logger.error("LP generation failed for lp=%s: %s", lp_id, exc, exc_info=True)
            lp.status = "ERROR"
            lp.error_message = str(exc)

        await db.commit()
        await db.refresh(lp)
        logger.info("GeneratedLP %s marked %s", lp_id, lp.status)

    await engine.dispose()
