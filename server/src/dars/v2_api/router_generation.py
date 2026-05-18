"""
F3.12 — Per-org usage report.
F3.13 — Class-lesson-slot detail with LP status surface.
F4.13 — Submit exam mastery results.
F5.14 — Failed LP/Exam retry.
F5.15 — Org-wide SLO coverage summary.

Endpoints take the per-org X-API-Key.
"""
import json
import logging
from datetime import date
from uuid import UUID

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from dars.breakdown.mastery_service import (
    PerQuestionResult,
    SubmitResultsInput,
    submit_exam_results,
)
from dars.config import settings
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

log = logging.getLogger("v2_api.generation")

router = APIRouter(prefix="/api/v1", tags=["generation"])


# ---------------------------------------------------------------------------
# F3.12 — usage report
# ---------------------------------------------------------------------------


@router.get("/orgs/me/usage")
async def get_org_usage(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> dict:
    """
    Returns LP + exam counts and cost_usd for the calling org.

    Attribution model (v1, per the plan): cost is attributed to the *creation
    org* — the first org that triggered the cache miss. In v1 the global
    pre-warm in F3.11 creates everything before any CST consumes, so the
    creation org for a global row is effectively "Dars system" (no org_id).

    For this v1 endpoint we surface the org's *class-scope* generations
    (rows with scope='class' and scope_ref_id ∈ this org's CSTs) so each
    org sees only what they directly caused. Global rows reused by all
    orgs do not double-count here.
    """
    # Build CST list for this org once.
    cst_rows = await conn.fetch(
        "SELECT id FROM class_subject_teachers WHERE org_id = $1",
        org.id,
    )
    cst_ids = [r["id"] for r in cst_rows]
    if not cst_ids:
        return {
            "lp_count": 0, "exam_count": 0, "total_cost_usd": 0.0,
            "by_subject": [], "by_curriculum": [],
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
        }

    date_params: list = []
    where_dates = ""
    if start:
        date_params.append(start)
        where_dates += f" AND created_at >= ${len(date_params) + 1}"  # placeholder offset; rebuilt below
    # Rebuild parameter list for both queries with predictable indices.

    lp_query = """
        SELECT subject_id, curriculum_id, cost_usd
        FROM generated_lps
        WHERE scope = 'class' AND scope_ref_id = ANY($1::UUID[])
    """
    exam_query = """
        SELECT subject_id, curriculum_id, cost_usd
        FROM generated_exams
        WHERE scope = 'class' AND scope_ref_id = ANY($1::UUID[])
    """
    lp_params: list = [cst_ids]
    exam_params: list = [cst_ids]
    if start:
        lp_params.append(start)
        exam_params.append(start)
        lp_query += f" AND created_at >= ${len(lp_params)}"
        exam_query += f" AND created_at >= ${len(exam_params)}"
    if end:
        lp_params.append(end)
        exam_params.append(end)
        lp_query += f" AND created_at <= ${len(lp_params)}"
        exam_query += f" AND created_at <= ${len(exam_params)}"

    lp_rows = await conn.fetch(lp_query, *lp_params)
    exam_rows = await conn.fetch(exam_query, *exam_params)

    # Subject + curriculum lookups for human-friendly response keys
    subject_lookup = {
        r["id"]: r["code"]
        for r in await conn.fetch("SELECT id, code FROM subjects")
    }
    curriculum_lookup = {
        r["id"]: r["code"]
        for r in await conn.fetch("SELECT id, code FROM curriculums")
    }

    def _sum_by(rows, key_fn):
        out: dict[str, dict] = {}
        for r in rows:
            label = key_fn(r) or "unknown"
            bucket = out.setdefault(label, {"count": 0, "cost_usd": 0.0})
            bucket["count"] += 1
            bucket["cost_usd"] += float(r["cost_usd"] or 0)
        return out

    total_cost = sum(float(r["cost_usd"] or 0) for r in lp_rows) + sum(
        float(r["cost_usd"] or 0) for r in exam_rows
    )

    by_subject_lp = _sum_by(lp_rows, lambda r: subject_lookup.get(r["subject_id"]))
    by_subject_exam = _sum_by(exam_rows, lambda r: subject_lookup.get(r["subject_id"]))
    by_subject = []
    for code in sorted(set(by_subject_lp) | set(by_subject_exam)):
        by_subject.append({
            "subject_code": code,
            "lp_count": by_subject_lp.get(code, {}).get("count", 0),
            "exam_count": by_subject_exam.get(code, {}).get("count", 0),
            "cost_usd": round(
                by_subject_lp.get(code, {}).get("cost_usd", 0)
                + by_subject_exam.get(code, {}).get("cost_usd", 0),
                4,
            ),
        })

    by_curriculum_lp = _sum_by(lp_rows, lambda r: curriculum_lookup.get(r["curriculum_id"]))
    by_curriculum_exam = _sum_by(exam_rows, lambda r: curriculum_lookup.get(r["curriculum_id"]))
    by_curriculum = []
    for code in sorted(set(by_curriculum_lp) | set(by_curriculum_exam)):
        by_curriculum.append({
            "curriculum_code": code,
            "lp_count": by_curriculum_lp.get(code, {}).get("count", 0),
            "exam_count": by_curriculum_exam.get(code, {}).get("count", 0),
            "cost_usd": round(
                by_curriculum_lp.get(code, {}).get("cost_usd", 0)
                + by_curriculum_exam.get(code, {}).get("cost_usd", 0),
                4,
            ),
        })

    return {
        "lp_count": len(lp_rows),
        "exam_count": len(exam_rows),
        "total_cost_usd": round(total_cost, 4),
        "by_subject": by_subject,
        "by_curriculum": by_curriculum,
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
    }


# ---------------------------------------------------------------------------
# F3.13 — class lesson slot detail with LP status surface
# ---------------------------------------------------------------------------


@router.get("/class-lesson-slots/{slot_id}")
async def get_class_lesson_slot_detail(
    slot_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> dict:
    """
    Detail view used by the teacher app (Phase 4) and admin dashboard
    (Phase 5). Always returns the slot, regardless of LP status. The
    LP fields are nullable when generation is still in flight.

    `lp_status` is the upstream pipeline state (PENDING/IN_FLIGHT/READY/
    ERROR/`not_generated`); the teacher app uses it to show "LP unavailable"
    while keeping the Mark Taught button enabled (D-50).
    """
    row = await conn.fetchrow(
        """
        SELECT
            cls.id, cls.cst_id, cls.position, cls.slot_type, cls.lp_type,
            cls.topic_id, cls.anchor_date, cls.status,
            cls.generated_lp_id, cls.org_id,
            t.topic_text,
            gl.status         AS lp_status,
            gl.content        AS lp_content,
            gl.error_message  AS lp_error_message,
            gl.tagging_status AS lp_tagging_status,
            gl.covered_sub_slo_ids AS lp_covered_sub_slo_ids
        FROM class_lesson_slots cls
        LEFT JOIN topics t        ON t.id = cls.topic_id
        LEFT JOIN generated_lps gl ON gl.id = cls.generated_lp_id
        WHERE cls.id = $1
        """,
        slot_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="lesson slot not found")
    if row["org_id"] != org.id:
        raise HTTPException(status_code=404, detail="lesson slot not found")

    return {
        "id": str(row["id"]),
        "cst_id": str(row["cst_id"]),
        "position": row["position"],
        "slot_type": row["slot_type"],
        "lp_type": row["lp_type"],
        "topic_id": str(row["topic_id"]) if row["topic_id"] else None,
        "topic_text": row["topic_text"],
        "anchor_date": row["anchor_date"].isoformat() if row["anchor_date"] else None,
        "status": row["status"],
        "lp_status": row["lp_status"] or "not_generated",
        "lp_content": row["lp_content"],
        "lp_error_message": row["lp_error_message"],
        "lp_tagging_status": row["lp_tagging_status"],
        "lp_covered_sub_slo_ids": (
            [str(x) for x in (row["lp_covered_sub_slo_ids"] or [])]
        ),
    }


# ---------------------------------------------------------------------------
# F4.13 — submit mastery results for an assessment slot
# ---------------------------------------------------------------------------


class PerQuestionBody(BaseModel):
    question_index: int = Field(ge=0)
    students_correct: int = Field(ge=0)
    marks_total: int = 1


class SubmitResultsBody(BaseModel):
    students_present: int = Field(gt=0)
    per_question: list[PerQuestionBody]
    assessed_on: date | None = None
    recorded_by_teacher_id: UUID | None = None


class SubmitResultsResponse(BaseModel):
    exam_result_id: UUID
    sub_slo_mastery_rows: int


@router.get("/class-assessment-slots/{slot_id}")
async def get_class_assessment_slot_detail(
    slot_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> dict:
    """
    Detail view used by the teacher app's mastery entry form and the
    "view exam" slide-over. Joins through generated_exams for the
    result JSON, exam_paper_html, status, tagging output.
    """
    row = await conn.fetchrow(
        """
        SELECT
            cas.id, cas.cst_id, cas.position, cas.assessment_type,
            cas.anchor_date, cas.status, cas.generated_exam_id, cas.org_id,
            ge.status                 AS exam_status,
            ge.result                 AS exam_result,
            ge.exam_paper_html        AS exam_paper_html,
            ge.question_sub_slo_tags  AS question_sub_slo_tags,
            ge.tagging_status         AS exam_tagging_status,
            ge.error_message          AS exam_error_message
        FROM class_assessment_slots cas
        LEFT JOIN generated_exams ge ON ge.id = cas.generated_exam_id
        WHERE cas.id = $1
        """,
        slot_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="assessment slot not found")
    if row["org_id"] != org.id:
        raise HTTPException(status_code=404, detail="assessment slot not found")

    topic_rows = await conn.fetch(
        """
        SELECT t.id, t.title
        FROM class_assessment_slot_topics cast2
        JOIN topics t ON t.id = cast2.topic_id
        WHERE cast2.class_assessment_slot_id = $1
        ORDER BY cast2.position
        """,
        slot_id,
    )

    return {
        "id": str(row["id"]),
        "cst_id": str(row["cst_id"]),
        "position": row["position"],
        "assessment_type": row["assessment_type"],
        "anchor_date": row["anchor_date"].isoformat() if row["anchor_date"] else None,
        "status": row["status"],
        "exam_status": row["exam_status"] or "not_generated",
        "exam_result": row["exam_result"],
        "exam_paper_html": row["exam_paper_html"],
        "question_sub_slo_tags": row["question_sub_slo_tags"],
        "exam_tagging_status": row["exam_tagging_status"],
        "exam_error_message": row["exam_error_message"],
        "topic_ids": [str(t["id"]) for t in topic_rows],
        "topic_titles": [t["title"] for t in topic_rows],
    }


@router.post(
    "/class-assessment-slots/{slot_id}/results",
    response_model=SubmitResultsResponse,
)
async def submit_class_assessment_results(
    slot_id: UUID,
    payload: SubmitResultsBody,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SubmitResultsResponse:
    """
    Record per-question correct counts for a completed assessment slot.
    Idempotent: resubmitting deletes the previous exam_results +
    sub_slo_mastery rows for this slot and re-creates them.

    Server walks the generated_exam.result tree in the same order
    iter_questions() (F3.9) uses, flattening to 0..N-1; clients submit
    `question_index` against that flat sequence.
    """
    # Tenancy: confirm the slot belongs to a CST in this org.
    org_check = await conn.fetchval(
        "SELECT org_id FROM class_assessment_slots WHERE id = $1",
        slot_id,
    )
    if org_check is None or org_check != org.id:
        raise HTTPException(status_code=404, detail="assessment slot not found")

    try:
        result = await submit_exam_results(
            conn,
            SubmitResultsInput(
                class_assessment_slot_id=slot_id,
                students_present=payload.students_present,
                recorded_by_teacher_id=payload.recorded_by_teacher_id,
                per_question=[
                    PerQuestionResult(
                        question_index=q.question_index,
                        students_correct=q.students_correct,
                        marks_total=q.marks_total,
                    )
                    for q in payload.per_question
                ],
                assessed_on=payload.assessed_on,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return SubmitResultsResponse(
        exam_result_id=result.exam_result_id,
        sub_slo_mastery_rows=result.sub_slo_mastery_rows,
    )


# ---------------------------------------------------------------------------
# F5.14 — Retry a failed LP / Exam generation
# ---------------------------------------------------------------------------


class RetryResponse(BaseModel):
    id: UUID
    status: str
    job_id: str | None


async def _resolve_lp_dispatch_inputs(
    conn: asyncpg.Connection, generated_lp_id: UUID
) -> tuple[str, str, str, str, str]:
    """Reconstruct (curriculum_code, grade_code, subject_code, topic_text,
    lp_type) for a retry. Uses topic_id when present; falls back to the
    revision-topics side table for revision LPs."""
    row = await conn.fetchrow(
        """
        SELECT gl.id, gl.lp_type, gl.topic_id, gl.revision_topic_set_hash,
               gl.curriculum_id, gl.grade_id, gl.subject_id,
               c.code AS curriculum_code,
               g.code AS grade_code,
               s.code AS subject_code,
               t.topic_text AS topic_text
        FROM generated_lps gl
        JOIN curriculums c ON c.id = gl.curriculum_id
        JOIN grades g ON g.id = gl.grade_id
        JOIN subjects s ON s.id = gl.subject_id
        LEFT JOIN topics t ON t.id = gl.topic_id
        WHERE gl.id = $1
        """,
        generated_lp_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="generated_lp not found")

    if row["topic_id"] is not None:
        if not row["topic_text"]:
            raise HTTPException(status_code=422, detail="topic has no text")
        return (
            row["curriculum_code"], row["grade_code"],
            row["subject_code"], row["topic_text"], row["lp_type"],
        )
    if row["revision_topic_set_hash"]:
        topic_rows = await conn.fetch(
            """
            SELECT t.topic_text
            FROM generated_lp_revision_topics grt
            JOIN topics t ON t.id = grt.topic_id
            WHERE grt.generated_lp_id = $1
            ORDER BY grt.position
            """,
            generated_lp_id,
        )
        page_content = "\n\n".join(
            (r["topic_text"] or "").strip()
            for r in topic_rows
            if (r["topic_text"] or "").strip()
        )
        if not page_content:
            raise HTTPException(status_code=422, detail="revision topics have no text")
        return (
            row["curriculum_code"], row["grade_code"],
            row["subject_code"], page_content, row["lp_type"],
        )
    raise HTTPException(status_code=422, detail="LP has neither topic nor revision set")


@router.post("/generated-lps/{generated_lp_id}/retry", response_model=RetryResponse)
async def retry_generated_lp(
    generated_lp_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> RetryResponse:
    """Dispatch a fresh LP-Assistant request for an ERROR (or PENDING-stuck)
    row. No-ops for already-READY rows.

    Tenancy: D-50 / phase doc — admins want to retry LPs for their own
    org's CSTs. For class-scope rows the scope_ref_id is the CST id and
    we check the CST's org_id. For global rows (cached, shared) we
    allow any org's admin to retry — they're shared infrastructure
    anyway and the result benefits everyone.
    """
    row = await conn.fetchrow(
        """
        SELECT gl.id, gl.status, gl.scope, gl.scope_ref_id,
               cst.org_id AS cst_org_id
        FROM generated_lps gl
        LEFT JOIN class_subject_teachers cst ON cst.id = gl.scope_ref_id
        WHERE gl.id = $1
        """,
        generated_lp_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="generated_lp not found")
    if row["scope"] == "class" and row["cst_org_id"] != org.id:
        raise HTTPException(status_code=404, detail="generated_lp not found")
    if row["status"] == "READY":
        return RetryResponse(id=generated_lp_id, status="READY", job_id=None)

    cur_code, grade_code, subj_code, page_content, lp_type = await _resolve_lp_dispatch_inputs(
        conn, generated_lp_id
    )

    callback_url = f"{settings.dars_base_url.rstrip('/')}/api/v1/webhooks/lp/{generated_lp_id}"
    # Reset to PENDING first so the row reflects in-flight state immediately.
    await conn.execute(
        """
        UPDATE generated_lps
        SET status = 'PENDING', error_message = NULL, updated_at = now()
        WHERE id = $1
        """,
        generated_lp_id,
    )
    try:
        req = LPRequest(
            curriculum_code=cur_code,
            grade=_parse_grade_int(grade_code),
            subject=subj_code,
            page_content=page_content,
            lp_type=lp_type,
            callback_url=callback_url,
        )
        job_id = await request_lp_generation(req)
    except Exception as exc:  # noqa: BLE001
        log.exception("retry_generated_lp: dispatch failed id=%s", generated_lp_id)
        await conn.execute(
            "UPDATE generated_lps SET status='ERROR', error_message=$1, updated_at=now() WHERE id=$2",
            f"retry dispatch failed: {exc}"[:2000], generated_lp_id,
        )
        return RetryResponse(id=generated_lp_id, status="ERROR", job_id=None)

    await conn.execute(
        "UPDATE generated_lps SET status='IN_FLIGHT', job_id=$1, updated_at=now() WHERE id=$2",
        job_id, generated_lp_id,
    )
    log.info("retry_generated_lp: id=%s job=%s", generated_lp_id, job_id)
    return RetryResponse(id=generated_lp_id, status="IN_FLIGHT", job_id=job_id)


@router.post("/generated-exams/{generated_exam_id}/retry", response_model=RetryResponse)
async def retry_generated_exam(
    generated_exam_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> RetryResponse:
    """Retry a failed exam. Reconstructs the payload from the assessment
    slot(s) that reference this generated_exam.
    """
    row = await conn.fetchrow(
        """
        SELECT ge.id, ge.status, ge.generation_type, ge.scope, ge.scope_ref_id,
               c.code AS curriculum_code,
               g.code AS grade_code,
               s.code AS subject_code,
               cst.org_id AS cst_org_id
        FROM generated_exams ge
        JOIN curriculums c ON c.id = ge.curriculum_id
        JOIN grades g ON g.id = ge.grade_id
        JOIN subjects s ON s.id = ge.subject_id
        LEFT JOIN class_subject_teachers cst ON cst.id = ge.scope_ref_id
        WHERE ge.id = $1
        """,
        generated_exam_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="generated_exam not found")
    if row["scope"] == "class" and row["cst_org_id"] != org.id:
        raise HTTPException(status_code=404, detail="generated_exam not found")
    if row["status"] == "READY":
        return RetryResponse(id=generated_exam_id, status="READY", job_id=None)

    # Find a slot that points at this exam, so we can rebuild the
    # page_content + question config.
    slot_id = await conn.fetchval(
        "SELECT id FROM class_assessment_slots WHERE generated_exam_id = $1 LIMIT 1",
        generated_exam_id,
    )
    if slot_id is None:
        raise HTTPException(
            status_code=422,
            detail="this generated_exam isn't linked to a class assessment slot; can't retry",
        )

    topic_rows = await conn.fetch(
        """
        SELECT t.topic_text
        FROM class_assessment_slot_topics cast2
        JOIN topics t ON t.id = cast2.topic_id
        WHERE cast2.class_assessment_slot_id = $1
        ORDER BY cast2.position
        """,
        slot_id,
    )
    page_content = "\n\n".join(
        (r["topic_text"] or "").strip()
        for r in topic_rows
        if (r["topic_text"] or "").strip()
    )
    if not page_content:
        raise HTTPException(status_code=422, detail="assessment slot has no topic text")

    # Re-use the batch-service default config heuristic so the same FA/SA
    # shape goes out. (Importing inline to avoid a circular at module
    # load.)
    from dars.generated_lps.batch_service import _config_for

    # Pick FA vs SA from the slot's assessment_type.
    a_type = await conn.fetchval(
        "SELECT assessment_type FROM class_assessment_slots WHERE id = $1", slot_id
    )
    long_type = "formative_assessment" if a_type == "formative" else "summative_assessment"
    config = _config_for(row["subject_code"], long_type)
    if config is None:
        raise HTTPException(
            status_code=422,
            detail=f"no default config for subject={row['subject_code']!r} type={long_type}",
        )

    callback_url = f"{settings.dars_base_url.rstrip('/')}/api/v1/webhooks/exam/{generated_exam_id}"
    await conn.execute(
        """
        UPDATE generated_exams
        SET status = 'PENDING', error_message = NULL, updated_at = now()
        WHERE id = $1
        """,
        generated_exam_id,
    )
    try:
        req = ExamRequest(
            curriculum_code=row["curriculum_code"],
            grade=_parse_grade_int(row["grade_code"]),
            subject=row["subject_code"],
            page_content=page_content,
            callback_url=callback_url,
            generation_type=row["generation_type"],
            **config,
        )
        job_id = await request_exam_generation(req)
    except Exception as exc:  # noqa: BLE001
        log.exception("retry_generated_exam: dispatch failed id=%s", generated_exam_id)
        await conn.execute(
            "UPDATE generated_exams SET status='ERROR', error_message=$1, updated_at=now() WHERE id=$2",
            f"retry dispatch failed: {exc}"[:2000], generated_exam_id,
        )
        return RetryResponse(id=generated_exam_id, status="ERROR", job_id=None)

    await conn.execute(
        "UPDATE generated_exams SET status='IN_FLIGHT', job_id=$1, updated_at=now() WHERE id=$2",
        job_id, generated_exam_id,
    )
    log.info("retry_generated_exam: id=%s job=%s", generated_exam_id, job_id)
    return RetryResponse(id=generated_exam_id, status="IN_FLIGHT", job_id=job_id)


# ---------------------------------------------------------------------------
# F5.14 — List failed generations for the dashboard
# ---------------------------------------------------------------------------


class FailureLPListItem(BaseModel):
    id: UUID
    cache_key: str | None
    scope: str
    scope_ref_id: UUID | None
    topic_id: UUID | None
    lp_type: str | None
    error_message: str | None
    created_at: str


class FailureExamListItem(BaseModel):
    id: UUID
    cache_key: str | None
    scope: str
    scope_ref_id: UUID | None
    generation_type: str | None
    error_message: str | None
    created_at: str


class FailureListResponse(BaseModel):
    lps: list[FailureLPListItem]
    exams: list[FailureExamListItem]


@router.get("/orgs/me/generation-failures", response_model=FailureListResponse)
async def list_generation_failures(
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> FailureListResponse:
    """LPs + exams in status=ERROR that this org can see.

    Includes:
      - All class-scope rows whose CST is in this org.
      - All global-scope rows (shared; any admin can retry).
    """
    lp_rows = await conn.fetch(
        """
        SELECT gl.id, gl.cache_key, gl.scope, gl.scope_ref_id, gl.topic_id,
               gl.lp_type, gl.error_message,
               to_char(gl.created_at, 'YYYY-MM-DD"T"HH24:MI:SSOF') AS created_at
        FROM generated_lps gl
        LEFT JOIN class_subject_teachers cst ON cst.id = gl.scope_ref_id
        WHERE gl.status = 'ERROR'
          AND (gl.scope = 'global' OR cst.org_id = $1)
        ORDER BY gl.created_at DESC
        LIMIT 200
        """,
        org.id,
    )
    exam_rows = await conn.fetch(
        """
        SELECT ge.id, ge.cache_key, ge.scope, ge.scope_ref_id,
               ge.generation_type, ge.error_message,
               to_char(ge.created_at, 'YYYY-MM-DD"T"HH24:MI:SSOF') AS created_at
        FROM generated_exams ge
        LEFT JOIN class_subject_teachers cst ON cst.id = ge.scope_ref_id
        WHERE ge.status = 'ERROR'
          AND (ge.scope = 'global' OR cst.org_id = $1)
        ORDER BY ge.created_at DESC
        LIMIT 200
        """,
        org.id,
    )
    return FailureListResponse(
        lps=[FailureLPListItem(**dict(r)) for r in lp_rows],
        exams=[FailureExamListItem(**dict(r)) for r in exam_rows],
    )


# ---------------------------------------------------------------------------
# F5.15 — Org-wide SLO coverage summary
# ---------------------------------------------------------------------------


class SLOCoverageBucket(BaseModel):
    slo_id: UUID
    slo_code: str
    slo_statement: str
    sub_slo_count: int
    taught_count: int
    avg_mastery_percent: float | None  # null when nothing assessed


class SLOCoverageSummaryResponse(BaseModel):
    items: list[SLOCoverageBucket]


@router.get(
    "/orgs/me/coverage-summary",
    response_model=SLOCoverageSummaryResponse,
)
async def get_org_coverage_summary(
    grade_id: UUID | None = Query(default=None),
    subject_id: UUID | None = Query(default=None),
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SLOCoverageSummaryResponse:
    """Aggregate per-SLO coverage across all CSTs in the org, optionally
    filtered by grade/subject.

    `taught_count` = number of distinct (cst_id, sub_slo_id) pairs where
    `cst_sub_slo_coverage.status = 'taught'`, across all CSTs that include
    that sub-SLO via `topic_sub_slos` linked to their class_lesson_slots.
    """
    filters = ["s.curriculum_id = $1"]
    params: list = [org.curriculum_id]
    if grade_id is not None:
        params.append(grade_id)
        filters.append(f"s.grade_id = ${len(params)}")
    if subject_id is not None:
        params.append(subject_id)
        filters.append(f"s.subject_id = ${len(params)}")

    params.append(org.id)
    org_param = f"${len(params)}"
    where_sql = " AND ".join(filters)

    rows = await conn.fetch(
        f"""
        WITH slo_universe AS (
            SELECT s.id        AS slo_id,
                   s.code      AS slo_code,
                   s.statement AS slo_statement
            FROM slos s
            WHERE {where_sql}
        ),
        sub_slos_per_slo AS (
            SELECT ss.slo_id, ss.id AS sub_slo_id
            FROM sub_slos ss
            WHERE ss.slo_id IN (SELECT slo_id FROM slo_universe)
        ),
        org_csts AS (
            SELECT cst.id AS cst_id
            FROM class_subject_teachers cst
            WHERE cst.org_id = {org_param}
        ),
        taught AS (
            SELECT DISTINCT cssc.cst_id, cssc.sub_slo_id
            FROM cst_sub_slo_coverage cssc
            JOIN org_csts oc ON oc.cst_id = cssc.cst_id
            WHERE cssc.status = 'taught'
        ),
        mastery AS (
            SELECT m.sub_slo_id, AVG(m.mastery_percent) AS avg_pct
            FROM sub_slo_mastery m
            JOIN org_csts oc ON oc.cst_id = m.cst_id
            GROUP BY m.sub_slo_id
        )
        SELECT
            u.slo_id, u.slo_code, u.slo_statement,
            COUNT(DISTINCT sps.sub_slo_id)::INT AS sub_slo_count,
            COUNT(DISTINCT t.sub_slo_id)::INT AS taught_count,
            AVG(m.avg_pct)::FLOAT AS avg_mastery_percent
        FROM slo_universe u
        LEFT JOIN sub_slos_per_slo sps ON sps.slo_id = u.slo_id
        LEFT JOIN taught t ON t.sub_slo_id = sps.sub_slo_id
        LEFT JOIN mastery m ON m.sub_slo_id = sps.sub_slo_id
        GROUP BY u.slo_id, u.slo_code, u.slo_statement
        ORDER BY u.slo_code
        """,
        *params,
    )

    return SLOCoverageSummaryResponse(
        items=[SLOCoverageBucket(**dict(r)) for r in rows],
    )
