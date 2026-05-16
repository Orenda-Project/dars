"""
F2.12 + F2.13 — Teacher-facing class slot actions + onboarding.

Auth: X-API-Key (per-org). All endpoints check that the targeted slot
or CST belongs to the calling org (Critical Rule #3).
"""
import logging
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from dars.breakdown.mark_taught_service import (
    mark_assessment_slot,
    mark_lesson_slot,
)
from dars.breakdown.onboarding_service import onboard_cst
from dars.v2_api.deps import OrgContext, get_current_org, get_db_conn
from dars.v2_api.schemas_class_actions import (
    CompleteAssessmentBody,
    MarkActionResponse,
    MarkTaughtBody,
    OnboardBody,
    OnboardResponse,
    SkipBody,
    SubSLOCoverageEntry,
    SubSLOCoverageResponse,
)

log = logging.getLogger("v2_api.class_actions")

router = APIRouter(prefix="/api/v2", tags=["v2-class-actions"])


# ---------------------------------------------------------------------------
# Helpers — enforce tenancy
# ---------------------------------------------------------------------------


async def _ensure_lesson_slot_in_org(
    conn: asyncpg.Connection, slot_id: UUID, org_id: UUID
) -> None:
    row = await conn.fetchval(
        "SELECT org_id FROM class_lesson_slots WHERE id = $1", slot_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="lesson slot not found")
    if row != org_id:
        raise HTTPException(status_code=404, detail="lesson slot not found")


async def _ensure_assessment_slot_in_org(
    conn: asyncpg.Connection, slot_id: UUID, org_id: UUID
) -> None:
    row = await conn.fetchval(
        "SELECT org_id FROM class_assessment_slots WHERE id = $1", slot_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="assessment slot not found")
    if row != org_id:
        raise HTTPException(status_code=404, detail="assessment slot not found")


async def _ensure_cst_in_org(
    conn: asyncpg.Connection, cst_id: UUID, org_id: UUID
) -> None:
    row = await conn.fetchval(
        "SELECT org_id FROM class_subject_teachers WHERE id = $1", cst_id
    )
    if row is None or row != org_id:
        raise HTTPException(status_code=404, detail="cst not found")


# ---------------------------------------------------------------------------
# F2.12 — mark-taught + skip + complete
# ---------------------------------------------------------------------------


@router.post(
    "/class-lesson-slots/{slot_id}/mark-taught",
    response_model=MarkActionResponse,
)
async def mark_lesson_taught(
    slot_id: UUID,
    payload: MarkTaughtBody,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> MarkActionResponse:
    await _ensure_lesson_slot_in_org(conn, slot_id, org.id)
    result = await mark_lesson_slot(
        conn,
        slot_id=slot_id,
        action="taught",
        occurred_on=payload.taught_on,
        notes=payload.notes,
    )
    return MarkActionResponse(**result.__dict__)


@router.post(
    "/class-lesson-slots/{slot_id}/skip",
    response_model=MarkActionResponse,
)
async def skip_lesson(
    slot_id: UUID,
    payload: SkipBody,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> MarkActionResponse:
    await _ensure_lesson_slot_in_org(conn, slot_id, org.id)
    result = await mark_lesson_slot(
        conn,
        slot_id=slot_id,
        action="skipped",
        occurred_on=payload.occurred_on,
        notes=payload.reason,
    )
    return MarkActionResponse(**result.__dict__)


@router.post(
    "/class-assessment-slots/{slot_id}/complete",
    response_model=MarkActionResponse,
)
async def complete_assessment(
    slot_id: UUID,
    payload: CompleteAssessmentBody,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> MarkActionResponse:
    await _ensure_assessment_slot_in_org(conn, slot_id, org.id)
    result = await mark_assessment_slot(
        conn,
        slot_id=slot_id,
        action="completed",
        occurred_on=payload.taught_on,
        notes=payload.notes,
    )
    return MarkActionResponse(**result.__dict__)


@router.post(
    "/class-assessment-slots/{slot_id}/skip",
    response_model=MarkActionResponse,
)
async def skip_assessment(
    slot_id: UUID,
    payload: SkipBody,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> MarkActionResponse:
    await _ensure_assessment_slot_in_org(conn, slot_id, org.id)
    result = await mark_assessment_slot(
        conn,
        slot_id=slot_id,
        action="skipped",
        occurred_on=payload.occurred_on,
        notes=payload.reason,
    )
    return MarkActionResponse(**result.__dict__)


# ---------------------------------------------------------------------------
# F2.13 — mid-year onboarding
# ---------------------------------------------------------------------------


@router.post("/csts/{cst_id}/onboard", response_model=OnboardResponse)
async def onboard(
    cst_id: UUID,
    payload: OnboardBody,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> OnboardResponse:
    await _ensure_cst_in_org(conn, cst_id, org.id)
    try:
        result = await onboard_cst(
            conn,
            cst_id=cst_id,
            chapter_position=payload.chapter_position,
            chapter_day=payload.chapter_day,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    return OnboardResponse(**result.__dict__)


# ---------------------------------------------------------------------------
# F2.12 — sub-SLO coverage report
# ---------------------------------------------------------------------------


@router.get(
    "/csts/{cst_id}/sub-slo-coverage",
    response_model=SubSLOCoverageResponse,
)
async def get_sub_slo_coverage(
    cst_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SubSLOCoverageResponse:
    """
    Return per-sub-SLO coverage status for the CST.

    Definitions per D-5 + D-12:
      'taught'      — a class_lesson_slot has been marked taught and the
                      sub-SLO is linked to that slot's topic.
      'not_taught'  — no taught record exists, but the lesson slot
                      that would cover it has position >= joined_at_position.
      'unknown'     — pre-onboarding position: the teacher joined mid-year
                      and this sub-SLO sits behind joined_at_position.

    Sub-SLO universe is everything linked (via topic_sub_slos) to any
    topic that appears in this CST's class_lesson_slots.
    """
    await _ensure_cst_in_org(conn, cst_id, org.id)

    state = await conn.fetchrow(
        "SELECT joined_at_position FROM cst_state WHERE cst_id = $1",
        cst_id,
    )
    joined_at = state["joined_at_position"] if state else 1

    # Build the universe + map each sub-SLO to its earliest lesson position.
    rows = await conn.fetch(
        """
        SELECT
            ss.id AS sub_slo_id,
            ss.code AS sub_slo_code,
            MIN(cls.position) AS first_position
        FROM class_lesson_slots cls
        JOIN topic_sub_slos tss ON tss.topic_id = cls.topic_id
        JOIN sub_slos ss ON ss.id = tss.sub_slo_id
        WHERE cls.cst_id = $1
        GROUP BY ss.id, ss.code
        ORDER BY ss.code
        """,
        cst_id,
    )
    coverage_rows = await conn.fetch(
        "SELECT sub_slo_id, status FROM cst_sub_slo_coverage WHERE cst_id = $1",
        cst_id,
    )
    taught = {r["sub_slo_id"] for r in coverage_rows if r["status"] == "taught"}

    items: list[SubSLOCoverageEntry] = []
    for r in rows:
        if r["sub_slo_id"] in taught:
            status_ = "taught"
        elif r["first_position"] < joined_at:
            status_ = "unknown"
        else:
            status_ = "not_taught"
        items.append(
            SubSLOCoverageEntry(
                sub_slo_id=r["sub_slo_id"],
                sub_slo_code=r["sub_slo_code"],
                status=status_,
            )
        )
    return SubSLOCoverageResponse(
        cst_id=cst_id,
        joined_at_position=joined_at,
        items=items,
    )
