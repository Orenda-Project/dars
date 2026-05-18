"""
F3.12 — Per-org usage report.
F3.13 — Class-lesson-slot detail with LP status surface.
F4.13 — Submit exam mastery results.

Endpoints take the per-org X-API-Key.
"""
import logging
from datetime import date
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from dars.breakdown.mastery_service import (
    PerQuestionResult,
    SubmitResultsInput,
    submit_exam_results,
)
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
