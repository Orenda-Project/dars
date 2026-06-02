"""
F2.12 + F2.13 — Teacher-facing class slot actions + onboarding.

Auth: X-API-Key (per-org). All endpoints check that the targeted slot
or CST belongs to the calling org (Critical Rule #3).
"""
import logging
from datetime import date as date_cls
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from dars.breakdown.chapter_plan_service import (
    _cst_weekday_set,
    chapter_slot_count,
    generate_chapter_plan,
    resolve_cst_syllabus_context,
)
from dars.breakdown.mark_taught_service import (
    mark_assessment_slot,
    mark_lesson_slot,
)
from dars.breakdown.onboarding_service import onboard_cst
from dars.breakdown.projector import project_cst_schedule
from dars.v2_api.deps import OrgContext, get_current_org, get_db_conn
from dars.v2_api.schemas_class_actions import (
    ClassAssessmentSlotListItem,
    ClassAssessmentSlotListResponse,
    ClassLessonSlotListItem,
    ClassLessonSlotListResponse,
    CompleteAssessmentBody,
    CstTimelineResponse,
    GenerateChapterPlanResponse,
    MarkActionResponse,
    MarkTaughtBody,
    OnboardBody,
    OnboardResponse,
    SkipBody,
    SubSLOCoverageEntry,
    SubSLOCoverageResponse,
    SyllabusChapterForCst,
    SyllabusForCstResponse,
    TimelineAssessmentItem,
    TimelineLessonItem,
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


# ---------------------------------------------------------------------------
# F4.6/F4.7 — Class slot list endpoints
#
# Used by the teacher app's class-detail page to render the Lessons and
# Assessments tabs in one call (grouped by breakdown chapter, with
# topic titles and LP/exam status joined in so the UI doesn't N+1).
# ---------------------------------------------------------------------------


@router.get(
    "/csts/{cst_id}/lesson-slots",
    response_model=ClassLessonSlotListResponse,
)
async def list_lesson_slots(
    cst_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> ClassLessonSlotListResponse:
    await _ensure_cst_in_org(conn, cst_id, org.id)

    rows = await conn.fetch(
        """
        SELECT
            cls.id, cls.cst_id, cls.position, cls.slot_type, cls.lp_type,
            cls.topic_id, cls.anchor_date, cls.status, cls.generated_lp_id,
            t.title              AS topic_title,
            book_chapter.id      AS breakdown_chapter_id,
            book_chapter.chapter_number AS breakdown_chapter_position,
            book_chapter.title   AS breakdown_chapter_title,
            gl.status            AS lp_status
        FROM class_lesson_slots cls
        LEFT JOIN book_chapters book_chapter ON book_chapter.id = cls.book_chapter_id
        LEFT JOIN topics t          ON t.id = cls.topic_id
        LEFT JOIN generated_lps gl  ON gl.id = cls.generated_lp_id
        WHERE cls.cst_id = $1
        ORDER BY cls.position
        """,
        cst_id,
    )

    items = [
        ClassLessonSlotListItem(
            id=r["id"], cst_id=r["cst_id"],
            position=r["position"], slot_type=r["slot_type"],
            lp_type=r["lp_type"], topic_id=r["topic_id"],
            topic_title=r["topic_title"], anchor_date=r["anchor_date"],
            status=r["status"], generated_lp_id=r["generated_lp_id"],
            lp_status=r["lp_status"] or "not_generated",
            breakdown_chapter_id=r["breakdown_chapter_id"],
            breakdown_chapter_position=r["breakdown_chapter_position"],
            breakdown_chapter_title=r["breakdown_chapter_title"],
        )
        for r in rows
    ]
    log.info(
        "list_lesson_slots: cst=%s returned %d slots", cst_id, len(items),
    )
    return ClassLessonSlotListResponse(cst_id=cst_id, items=items)


@router.get(
    "/csts/{cst_id}/assessment-slots",
    response_model=ClassAssessmentSlotListResponse,
)
async def list_assessment_slots(
    cst_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> ClassAssessmentSlotListResponse:
    await _ensure_cst_in_org(conn, cst_id, org.id)

    rows = await conn.fetch(
        """
        SELECT
            cas.id, cas.cst_id, cas.position, cas.assessment_type,
            cas.anchor_date, cas.status, cas.generated_exam_id,
            book_chapter.id      AS breakdown_chapter_id,
            book_chapter.chapter_number AS breakdown_chapter_position,
            book_chapter.title   AS breakdown_chapter_title,
            ge.status            AS exam_status,
            COALESCE(
                array_agg(cast2.topic_id ORDER BY cast2.position)
                    FILTER (WHERE cast2.topic_id IS NOT NULL),
                ARRAY[]::UUID[]
            ) AS topic_ids,
            COALESCE(
                array_agg(t.title ORDER BY cast2.position)
                    FILTER (WHERE t.title IS NOT NULL),
                ARRAY[]::TEXT[]
            ) AS topic_titles
        FROM class_assessment_slots cas
        LEFT JOIN book_chapters book_chapter ON book_chapter.id = cas.book_chapter_id
        LEFT JOIN class_assessment_slot_topics cast2
            ON cast2.class_assessment_slot_id = cas.id
        LEFT JOIN topics t            ON t.id = cast2.topic_id
        LEFT JOIN generated_exams ge  ON ge.id = cas.generated_exam_id
        WHERE cas.cst_id = $1
        GROUP BY cas.id, book_chapter.id, ge.status
        ORDER BY cas.position
        """,
        cst_id,
    )

    items = [
        ClassAssessmentSlotListItem(
            id=r["id"], cst_id=r["cst_id"], position=r["position"],
            assessment_type=r["assessment_type"],
            anchor_date=r["anchor_date"], status=r["status"],
            generated_exam_id=r["generated_exam_id"],
            exam_status=r["exam_status"] or "not_generated",
            topic_ids=list(r["topic_ids"] or []),
            topic_titles=list(r["topic_titles"] or []),
            breakdown_chapter_id=r["breakdown_chapter_id"],
            breakdown_chapter_position=r["breakdown_chapter_position"],
            breakdown_chapter_title=r["breakdown_chapter_title"],
        )
        for r in rows
    ]
    log.info(
        "list_assessment_slots: cst=%s returned %d slots", cst_id, len(items),
    )
    return ClassAssessmentSlotListResponse(cst_id=cst_id, items=items)


# ---------------------------------------------------------------------------
# class-timeline-view — unified, dated timeline (D-1..D-5).
#
# Merges the lesson + assessment list queries above with the projector's
# per-slot dates (project_cst_schedule, reused verbatim per D-5) into one
# kind-discriminated list sorted by global position. One fetch drives the
# teacher app's Timeline tab.
# ---------------------------------------------------------------------------


@router.get(
    "/csts/{cst_id}/timeline",
    response_model=CstTimelineResponse,
)
async def get_cst_timeline(
    cst_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> CstTimelineResponse:
    log.info("get_cst_timeline: entry cst=%s", cst_id)
    try:
        await _ensure_cst_in_org(conn, cst_id, org.id)

        # Projector owns date assignment + conflict/overflow flags (D-2, D-5).
        projected = await project_cst_schedule(conn, cst_id)
        proj = {(p.slot_kind, p.slot_id): p for p in projected}

        lesson_rows = await conn.fetch(
            """
            SELECT
                cls.id, cls.position, cls.slot_type, cls.lp_type,
                cls.topic_id, cls.status, cls.generated_lp_id,
                t.title              AS topic_title,
                book_chapter.id      AS breakdown_chapter_id,
                book_chapter.chapter_number AS breakdown_chapter_position,
                book_chapter.title   AS breakdown_chapter_title,
                gl.status            AS lp_status
            FROM class_lesson_slots cls
            LEFT JOIN book_chapters book_chapter ON book_chapter.id = cls.book_chapter_id
            LEFT JOIN topics t          ON t.id = cls.topic_id
            LEFT JOIN generated_lps gl  ON gl.id = cls.generated_lp_id
            WHERE cls.cst_id = $1
            ORDER BY cls.position
            """,
            cst_id,
        )

        assess_rows = await conn.fetch(
            """
            SELECT
                cas.id, cas.position, cas.assessment_type,
                cas.status, cas.generated_exam_id,
                book_chapter.id      AS breakdown_chapter_id,
                book_chapter.chapter_number AS breakdown_chapter_position,
                book_chapter.title   AS breakdown_chapter_title,
                ge.status            AS exam_status,
                COALESCE(
                    array_agg(cast2.topic_id ORDER BY cast2.position)
                        FILTER (WHERE cast2.topic_id IS NOT NULL),
                    ARRAY[]::UUID[]
                ) AS topic_ids,
                COALESCE(
                    array_agg(t.title ORDER BY cast2.position)
                        FILTER (WHERE t.title IS NOT NULL),
                    ARRAY[]::TEXT[]
                ) AS topic_titles
            FROM class_assessment_slots cas
            LEFT JOIN book_chapters book_chapter ON book_chapter.id = cas.book_chapter_id
            LEFT JOIN class_assessment_slot_topics cast2
                ON cast2.class_assessment_slot_id = cas.id
            LEFT JOIN topics t            ON t.id = cast2.topic_id
            LEFT JOIN generated_exams ge  ON ge.id = cas.generated_exam_id
            WHERE cas.cst_id = $1
            GROUP BY cas.id, book_chapter.id, ge.status
            ORDER BY cas.position
            """,
            cst_id,
        )

        items: list[TimelineLessonItem | TimelineAssessmentItem] = []

        for r in lesson_rows:
            p = proj.get(("lesson", r["id"]))
            items.append(TimelineLessonItem(
                id=r["id"], position=r["position"],
                projected_date=p.projected_date if p else None,
                is_anchor=p.is_anchor if p else False,
                is_conflict=p.is_conflict if p else False,
                is_overflow=p.is_overflow if p else False,
                slot_type=r["slot_type"], lp_type=r["lp_type"],
                topic_id=r["topic_id"], topic_title=r["topic_title"],
                status=r["status"], generated_lp_id=r["generated_lp_id"],
                lp_status=r["lp_status"] or "not_generated",
                breakdown_chapter_id=r["breakdown_chapter_id"],
                breakdown_chapter_position=r["breakdown_chapter_position"],
                breakdown_chapter_title=r["breakdown_chapter_title"],
            ))

        for r in assess_rows:
            p = proj.get(("assessment", r["id"]))
            items.append(TimelineAssessmentItem(
                id=r["id"], position=r["position"],
                projected_date=p.projected_date if p else None,
                is_anchor=p.is_anchor if p else False,
                is_conflict=p.is_conflict if p else False,
                is_overflow=p.is_overflow if p else False,
                assessment_type=r["assessment_type"],
                topic_ids=list(r["topic_ids"] or []),
                topic_titles=list(r["topic_titles"] or []),
                status=r["status"], generated_exam_id=r["generated_exam_id"],
                exam_status=r["exam_status"] or "not_generated",
                breakdown_chapter_id=r["breakdown_chapter_id"],
                breakdown_chapter_position=r["breakdown_chapter_position"],
                breakdown_chapter_title=r["breakdown_chapter_title"],
            ))

        # Global teaching order is the spine (D-1).
        items.sort(key=lambda i: i.position)

        log.info(
            "get_cst_timeline: exit cst=%s items=%d overflow=%d conflicts=%d",
            cst_id, len(items),
            sum(1 for i in items if i.is_overflow),
            sum(1 for i in items if i.is_conflict),
        )
        return CstTimelineResponse(cst_id=cst_id, items=items)
    except HTTPException:
        raise
    except Exception:
        log.error("get_cst_timeline: failed cst=%s", cst_id, exc_info=True)
        raise


# ---------------------------------------------------------------------------
# Teacher Chapter Plan — syllabus view + break-it-down (Phase 3)
# ---------------------------------------------------------------------------


def _pick_current_chapter(chapters: list[dict], today: date_cls) -> UUID | None:
    """D-10: the chapter whose date range contains today; else the next upcoming;
    else the last dated chapter. None if no chapter has dates."""
    dated = [c for c in chapters if c["start_date"] and c["end_date"]]
    if not dated:
        return None
    for c in dated:
        if c["start_date"] <= today <= c["end_date"]:
            return c["book_chapter_id"]
    upcoming = [c for c in dated if c["start_date"] > today]
    if upcoming:
        return min(upcoming, key=lambda c: c["start_date"])["book_chapter_id"]
    return max(dated, key=lambda c: c["end_date"])["book_chapter_id"]


@router.get("/csts/{cst_id}/syllabus", response_model=SyllabusForCstResponse)
async def get_cst_syllabus(
    cst_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SyllabusForCstResponse:
    """F3.1 — the class's syllabus (chapters + date ranges), each with its
    computed slot count and current/planned flags, positioned by today (D-10)."""
    log.info("get_cst_syllabus: entry cst=%s", cst_id)
    await _ensure_cst_in_org(conn, cst_id, org.id)
    ctx = await resolve_cst_syllabus_context(conn, cst_id)
    weekdays = await _cst_weekday_set(conn, cst_id)
    periods_per_week = len(weekdays)

    if ctx.syllabus_breakdown_id is None:
        return SyllabusForCstResponse(
            cst_id=cst_id, syllabus_breakdown_id=None,
            periods_per_week=periods_per_week, chapters=[],
        )

    rows = await conn.fetch(
        """
        SELECT sch.book_chapter_id, bc.chapter_number, bc.title,
               sch.start_date, sch.end_date
        FROM syllabus_chapters sch
        JOIN book_chapters bc ON bc.id = sch.book_chapter_id
        WHERE sch.syllabus_breakdown_id = $1
        ORDER BY bc.chapter_number
        """,
        ctx.syllabus_breakdown_id,
    )
    chapters = [dict(r) for r in rows]
    current_id = _pick_current_chapter(chapters, date_cls.today())

    # which chapters already have generated class slots?
    planned_ids = {
        r["book_chapter_id"]
        for r in await conn.fetch(
            """
            SELECT book_chapter_id FROM class_lesson_slots
              WHERE cst_id = $1 AND book_chapter_id IS NOT NULL
            UNION
            SELECT book_chapter_id FROM class_assessment_slots
              WHERE cst_id = $1 AND book_chapter_id IS NOT NULL
            """,
            cst_id,
        )
    }

    items: list[SyllabusChapterForCst] = []
    for c in chapters:
        items.append(SyllabusChapterForCst(
            book_chapter_id=c["book_chapter_id"],
            chapter_number=c["chapter_number"],
            title=c["title"],
            start_date=c["start_date"],
            end_date=c["end_date"],
            slot_count=await chapter_slot_count(
                conn, cst_id, c["start_date"], c["end_date"]
            ),
            is_planned=c["book_chapter_id"] in planned_ids,
            is_current=c["book_chapter_id"] == current_id,
        ))

    log.info(
        "get_cst_syllabus: exit cst=%s chapters=%d periods/wk=%d",
        cst_id, len(items), periods_per_week,
    )
    return SyllabusForCstResponse(
        cst_id=cst_id,
        syllabus_breakdown_id=ctx.syllabus_breakdown_id,
        periods_per_week=periods_per_week,
        chapters=items,
    )


@router.post(
    "/csts/{cst_id}/chapters/{book_chapter_id}/plan",
    response_model=GenerateChapterPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def break_down_chapter(
    cst_id: UUID,
    book_chapter_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> GenerateChapterPlanResponse:
    """F3.3 — "break it down": generate a chapter's Chapter Plan into the class
    slots, sized by the teacher's real timetable (D-9)."""
    log.info("break_down_chapter: entry cst=%s chapter=%s", cst_id, book_chapter_id)
    await _ensure_cst_in_org(conn, cst_id, org.id)
    try:
        result = await generate_chapter_plan(
            conn, cst_id=cst_id, book_chapter_id=book_chapter_id, org_id=org.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    log.info(
        "break_down_chapter: exit cst=%s chapter=%s slots=%d",
        cst_id, book_chapter_id, result.slot_count,
    )
    return GenerateChapterPlanResponse(
        cst_id=result.cst_id,
        book_chapter_id=result.book_chapter_id,
        slot_count=result.slot_count,
        lesson_slot_count=result.lesson_slot_count,
        assessment_slot_count=result.assessment_slot_count,
        warnings=result.warnings,
    )
