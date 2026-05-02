import asyncio
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

POLL_INTERVAL = 5   # seconds between status checks
POLL_TIMEOUT = 300  # give up after 5 minutes


async def queue_custom_exam_generation(
    db: AsyncSession,
    client_id: uuid.UUID,
    curriculum: str,
    request: CustomExamGenerationCreateRequest,
) -> CustomExamGeneration:
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
    logger.info("queue_custom_exam_generation: queued eg_id=%s client_id=%s", eg.id, client_id)
    return eg


async def get_custom_exam_generation(
    db: AsyncSession,
    client_id: uuid.UUID,
    eg_id: uuid.UUID,
) -> CustomExamGeneration | None:
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
    Background task: submit to UG_EG v2 async endpoint, poll for result, update record.
    Uses its own DB session (background tasks run outside request context).
    """
    logger.info("generate_custom_exam_task: eg_id=%s client_id=%s", eg_id, client_id)
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        eg = await db.get(CustomExamGeneration, eg_id)
        if eg is None:
            logger.error("generate_custom_exam_task: CustomExamGeneration %s not found", eg_id)
            await engine.dispose()
            return

        payload: dict = {
            "callback_url": "https://dars.taleemabad.com/noop",  # required by v2; we poll instead
            "generation_type": request.generation_type,
            "curriculum": curriculum,
            "grade": canonical_grade(request.grade),
            "subject": canonical_subject(request.subject),
            "page_ranges": request.page_ranges,
            "include_answer_key": request.include_answer_key,
            "image_generation_enabled": request.image_generation_enabled,
            "enable_review": request.enable_review,
            "question_types": request.question_types or ["seen", "unseen"],
        }
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
            async with httpx.AsyncClient(timeout=30.0) as http:
                # Submit to v2 async endpoint
                submit_resp = await http.post(
                    f"{settings.eg_assistant_url}/api/v2/generate-exam",
                    json=payload,
                    headers={"api-key": settings.eg_assistant_api_key},
                )
                if submit_resp.is_error:
                    logger.error(
                        "EG v2 submit error for eg=%s: HTTP %s — %s",
                        eg_id, submit_resp.status_code, submit_resp.text,
                    )
                    submit_resp.raise_for_status()

                job_id = submit_resp.json().get("job_id")
                if not job_id:
                    raise ValueError("EG v2 did not return job_id")

                logger.info("generate_custom_exam_task: eg=%s submitted job_id=%s", eg_id, job_id)
                eg.eg_job_id = job_id
                await db.commit()

            # Poll for result
            elapsed = 0
            result_data = None
            async with httpx.AsyncClient(timeout=15.0) as http:
                while elapsed < POLL_TIMEOUT:
                    await asyncio.sleep(POLL_INTERVAL)
                    elapsed += POLL_INTERVAL

                    status_resp = await http.get(
                        f"{settings.eg_assistant_url}/api/v2/webhook-status/{job_id}",
                        headers={"api-key": settings.eg_assistant_api_key},
                    )
                    if status_resp.is_error:
                        logger.warning(
                            "generate_custom_exam_task: status poll failed eg=%s job=%s HTTP %s",
                            eg_id, job_id, status_resp.status_code,
                        )
                        continue

                    body = status_resp.json()
                    job_status = body.get("job_status")
                    logger.info(
                        "generate_custom_exam_task: eg=%s job=%s status=%s elapsed=%ds",
                        eg_id, job_id, job_status, elapsed,
                    )

                    if job_status == "completed":
                        result_data = body.get("data")
                        break
                    elif job_status == "error":
                        error_msg = body.get("data", {}).get("error", "unknown error from EG")
                        raise ValueError(f"EG job failed: {error_msg}")
                    # still "processing" — keep polling

            if result_data is None:
                raise TimeoutError(f"EG job {job_id} did not complete within {POLL_TIMEOUT}s")

            eg.result = result_data
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
