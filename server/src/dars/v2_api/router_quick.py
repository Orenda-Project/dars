"""
F4.14 — Quick LP + Quick Exam.

Power-user / sample-app endpoints. Unlike the cached pipeline:
  - no cache lookup (every call generates a new LP / exam)
  - no class-slot link
  - inserts a row in generated_lps / generated_exams so the FE can poll
    the existing /refresh endpoint to follow status, and so the audit
    trail + cost tracking still apply

The LP/Exam still go through LP Assistant / UG_EG via the async webhook
model. The client gets back a row id immediately and polls.
"""
import logging
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from dars.config import settings
from dars.generated_exams.service import (
    build_cache_key_global as _build_exam_cache_key_global,  # noqa: F401 — unused but documented
)
from dars.generated_exams.ug_eg_client import (
    ExamRequest,
    request_exam_generation,
)
from dars.generated_lps.lp_assistant_client import (
    LPRequest,
    request_lp_generation,
)
from dars.generated_lps.service import _parse_grade_int
from dars.v2_api.deps import OrgContext, get_current_org, get_db_conn

log = logging.getLogger("v2_api.quick")

router = APIRouter(prefix="/api/v1", tags=["quick"])


# ---------------------------------------------------------------------------
# Quick LP
# ---------------------------------------------------------------------------


class QuickLPBody(BaseModel):
    curriculum_code: str
    grade: int = Field(ge=1, le=5)
    subject: str
    page_content: str
    lp_type: str
    class_strength: int = 30
    generate_bilingual: bool = False


class QuickGenerationCreated(BaseModel):
    id: UUID
    status: str   # 'PENDING' | 'IN_FLIGHT' | 'ERROR' (success path is IN_FLIGHT)
    job_id: str | None


@router.post("/quick-lp", response_model=QuickGenerationCreated)
async def quick_lp(
    payload: QuickLPBody,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> QuickGenerationCreated:
    """Generate a one-off LP without touching the cache.

    Returns immediately with the new generated_lps.id. The client polls
    `/api/v1/generated-lps/{id}/refresh` or waits for the webhook.
    """
    # Look up curriculum/grade/subject ids for the row (FK constraints
    # require these). The values surface back via the row only; we
    # don't need them for the LP Assistant call.
    cur_id = await conn.fetchval(
        "SELECT id FROM curriculums WHERE code = $1", payload.curriculum_code,
    )
    if cur_id is None:
        raise HTTPException(status_code=422, detail=f"unknown curriculum_code={payload.curriculum_code!r}")
    grade_id = await conn.fetchval(
        "SELECT id FROM grades WHERE code = $1", f"G{payload.grade}",
    )
    if grade_id is None:
        raise HTTPException(status_code=422, detail=f"grade={payload.grade} not seeded")
    subject_id = await conn.fetchval(
        "SELECT id FROM subjects WHERE code = $1", payload.subject,
    )
    if subject_id is None:
        raise HTTPException(status_code=422, detail=f"unknown subject={payload.subject!r}")

    # Insert PENDING row with cache_key=NULL so it never satisfies a
    # cache lookup. Belongs to this org via scope_ref_id under 'class'
    # scope? No — `class` requires a cst_id and we don't have one. Use
    # 'global' + null cache_key (the partial unique index only enforces
    # uniqueness when cache_key IS NOT NULL).
    new_id = await conn.fetchval(
        """
        INSERT INTO generated_lps (
            cache_key, scope, scope_ref_id,
            curriculum_id, grade_id, subject_id,
            topic_id, lp_type, status
        ) VALUES (NULL, 'global', NULL, $1, $2, $3, NULL, $4, 'PENDING')
        RETURNING id
        """,
        cur_id, grade_id, subject_id, payload.lp_type,
    )

    callback_url = f"{settings.dars_base_url.rstrip('/')}/api/v1/webhooks/lp/{new_id}"
    try:
        req = LPRequest(
            curriculum_code=payload.curriculum_code,
            grade=payload.grade,
            subject=payload.subject,
            page_content=payload.page_content,
            lp_type=payload.lp_type,
            callback_url=callback_url,
            class_strength=payload.class_strength,
            generate_bilingual=payload.generate_bilingual,
        )
        job_id = await request_lp_generation(req)
    except Exception as exc:  # noqa: BLE001
        log.exception("quick_lp: dispatch failed id=%s", new_id)
        await conn.execute(
            "UPDATE generated_lps SET status='ERROR', error_message=$1, updated_at=now() WHERE id=$2",
            str(exc)[:2000], new_id,
        )
        return QuickGenerationCreated(id=new_id, status="ERROR", job_id=None)

    await conn.execute(
        "UPDATE generated_lps SET status='IN_FLIGHT', job_id=$1, updated_at=now() WHERE id=$2",
        job_id, new_id,
    )
    log.info("quick_lp: org=%s id=%s job=%s", org.id, new_id, job_id)
    return QuickGenerationCreated(id=new_id, status="IN_FLIGHT", job_id=job_id)


# ---------------------------------------------------------------------------
# Quick Exam
# ---------------------------------------------------------------------------


class QuickExamBody(BaseModel):
    curriculum_code: str
    grade: int = Field(ge=1, le=5)
    subject: str
    page_content: str
    generation_type: str = "exam"
    question_types: list[str] = Field(default_factory=lambda: ["unseen"])
    unseen_categories: list[str] = Field(default_factory=list)
    unseen_objective_types: list[str] = Field(default_factory=list)
    unseen_subjective_types: list[str] = Field(default_factory=list)
    unseen_objective_counts: dict[str, int] = Field(default_factory=dict)
    unseen_subjective_counts: dict[str, int] = Field(default_factory=dict)
    long_question_sub_types: list[str] = Field(default_factory=list)
    include_answer_key: bool = True


@router.post("/quick-exam", response_model=QuickGenerationCreated)
async def quick_exam(
    payload: QuickExamBody,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> QuickGenerationCreated:
    cur_id = await conn.fetchval(
        "SELECT id FROM curriculums WHERE code = $1", payload.curriculum_code,
    )
    if cur_id is None:
        raise HTTPException(status_code=422, detail=f"unknown curriculum_code={payload.curriculum_code!r}")
    grade_id = await conn.fetchval(
        "SELECT id FROM grades WHERE code = $1", f"G{payload.grade}",
    )
    if grade_id is None:
        raise HTTPException(status_code=422, detail=f"grade={payload.grade} not seeded")
    subject_id = await conn.fetchval(
        "SELECT id FROM subjects WHERE code = $1", payload.subject,
    )
    if subject_id is None:
        raise HTTPException(status_code=422, detail=f"unknown subject={payload.subject!r}")

    # Insert PENDING with cache_key=NULL.
    new_id = await conn.fetchval(
        """
        INSERT INTO generated_exams (
            cache_key, scope, scope_ref_id,
            curriculum_id, grade_id, subject_id,
            topic_ids_hash, generation_type, question_config_hash, status
        ) VALUES (NULL, 'global', NULL, $1, $2, $3, '', $4, '', 'PENDING')
        RETURNING id
        """,
        cur_id, grade_id, subject_id, payload.generation_type,
    )

    callback_url = f"{settings.dars_base_url.rstrip('/')}/api/v1/webhooks/exam/{new_id}"
    try:
        req = ExamRequest(
            curriculum_code=payload.curriculum_code,
            grade=payload.grade,
            subject=payload.subject,
            page_content=payload.page_content,
            callback_url=callback_url,
            generation_type=payload.generation_type,
            question_types=payload.question_types,
            unseen_categories=payload.unseen_categories,
            unseen_objective_types=payload.unseen_objective_types,
            unseen_subjective_types=payload.unseen_subjective_types,
            unseen_objective_counts=payload.unseen_objective_counts,
            unseen_subjective_counts=payload.unseen_subjective_counts,
            long_question_sub_types=payload.long_question_sub_types,
            include_answer_key=payload.include_answer_key,
        )
        job_id = await request_exam_generation(req)
    except Exception as exc:  # noqa: BLE001
        log.exception("quick_exam: dispatch failed id=%s", new_id)
        await conn.execute(
            "UPDATE generated_exams SET status='ERROR', error_message=$1, updated_at=now() WHERE id=$2",
            str(exc)[:2000], new_id,
        )
        return QuickGenerationCreated(id=new_id, status="ERROR", job_id=None)

    await conn.execute(
        "UPDATE generated_exams SET status='IN_FLIGHT', job_id=$1, updated_at=now() WHERE id=$2",
        job_id, new_id,
    )
    log.info("quick_exam: org=%s id=%s job=%s", org.id, new_id, job_id)
    return QuickGenerationCreated(id=new_id, status="IN_FLIGHT", job_id=job_id)
