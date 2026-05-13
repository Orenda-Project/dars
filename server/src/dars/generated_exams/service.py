import asyncio
import logging

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dars.config import settings
from dars.generated_exams.models import GeneratedExam
from dars.generated_exams.schemas import GeneratedExamCreate
from dars.lookup.service import validate_grade, validate_subject
from dars.mapping import canonical_grade, canonical_subject

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5   # seconds between status checks
POLL_TIMEOUT = 300  # give up after 5 minutes


async def create_generated_exam(
    db: AsyncSession,
    client_id: int,
    data: GeneratedExamCreate,
    curriculum: str,
) -> GeneratedExam:
    """Create a PENDING generated exam record and return it. Background task fires separately."""
    logger.info(
        "create_generated_exam: client_id=%s curriculum=%s grade=%s subject=%s type=%s",
        client_id, curriculum, data.grade, data.subject, data.generation_type,
    )
    await validate_grade(db, data.grade)
    await validate_subject(db, data.subject)
    exam = GeneratedExam(
        client_id=client_id,
        curriculum=curriculum,
        grade=data.grade,
        subject=data.subject,
        page_ranges=data.page_ranges,
        generation_type=data.generation_type,
        external_id=data.external_id,
        status="PENDING",
    )
    db.add(exam)
    await db.commit()
    await db.refresh(exam)
    logger.info("create_generated_exam: queued exam_id=%s client_id=%s", exam.id, client_id)
    return exam


async def get_generated_exam(
    db: AsyncSession,
    exam_id: int,
    client_id: int,
) -> GeneratedExam | None:
    """Fetch a single generated exam, always filtering by client_id."""
    result = await db.execute(
        select(GeneratedExam).where(
            GeneratedExam.id == exam_id,
            GeneratedExam.client_id == client_id,
        )
    )
    return result.scalar_one_or_none()


async def list_generated_exams(
    db: AsyncSession,
    client_id: int,
    external_id: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[GeneratedExam], int]:
    """Return (items, total) for paginated generated exam list, filtered by client_id."""
    base_filter = [GeneratedExam.client_id == client_id]
    if external_id is not None:
        base_filter.append(GeneratedExam.external_id == external_id)

    count_result = await db.execute(
        select(func.count()).select_from(GeneratedExam).where(*base_filter)
    )
    total = count_result.scalar_one()

    items_result = await db.execute(
        select(GeneratedExam)
        .where(*base_filter)
        .order_by(GeneratedExam.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = list(items_result.scalars().all())
    return items, total


async def generate_exam_task(
    exam_id: int,
    client_id: int,
    curriculum: str,
    request: GeneratedExamCreate,
) -> None:
    """
    Background task: submit to UG_EG v2 async endpoint, poll for result, update record.
    Uses its own DB session (background tasks run outside request context).
    """
    logger.info("generate_exam_task: exam_id=%s client_id=%s", exam_id, client_id)
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with factory() as db:
            exam = await db.get(GeneratedExam, exam_id)
            if exam is None:
                logger.error("generate_exam_task: GeneratedExam %s not found", exam_id)
                return

            payload: dict = {
                "callback_url": "https://dars.taleemabad.com/noop",
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
                    submit_resp = await http.post(
                        f"{settings.eg_assistant_url}/api/v2/generate-exam",
                        json=payload,
                        headers={"api-key": settings.eg_assistant_api_key},
                    )
                    if submit_resp.is_error:
                        logger.error(
                            "EG v2 submit error for exam=%s: HTTP %s — %s",
                            exam_id, submit_resp.status_code, submit_resp.text,
                        )
                        submit_resp.raise_for_status()

                    job_id = submit_resp.json().get("job_id")
                    if not job_id:
                        raise ValueError("EG v2 did not return job_id")

                    logger.info("generate_exam_task: exam=%s submitted job_id=%s", exam_id, job_id)
                    exam.eg_job_id = job_id
                    await db.commit()

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
                                "generate_exam_task: status poll failed exam=%s job=%s HTTP %s",
                                exam_id, job_id, status_resp.status_code,
                            )
                            continue

                        body = status_resp.json()
                        job_status = body.get("job_status")
                        logger.info(
                            "generate_exam_task: exam=%s job=%s status=%s elapsed=%ds",
                            exam_id, job_id, job_status, elapsed,
                        )

                        if job_status == "completed":
                            result_data = body.get("data")
                            break
                        elif job_status == "error":
                            error_msg = body.get("data", {}).get("error", "unknown error from EG")
                            raise ValueError(f"EG job failed: {error_msg}")

                if result_data is None:
                    raise TimeoutError(f"EG job {job_id} did not complete within {POLL_TIMEOUT}s")

                exam.result = result_data
                exam.status = "READY"

            except Exception as exc:
                logger.error("Exam generation failed for exam=%s: %s", exam_id, exc, exc_info=True)
                exam.error_message = str(exc)
                exam.status = "ERROR"

            await db.commit()
            await db.refresh(exam)
            logger.info("GeneratedExam %s marked %s", exam_id, exam.status)

    except Exception as exc:
        logger.error("generate_exam_task: DB error for exam_id=%s: %s", exam_id, exc, exc_info=True)
    finally:
        await engine.dispose()
