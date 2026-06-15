"""
F2.12 + F2.13 — Teacher-facing class slot actions + onboarding.

Auth: X-API-Key (per-org). All endpoints check that the targeted slot
or CST belongs to the calling org (Critical Rule #3).
"""
import logging
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from dars.breakdown.chapter_plan_service import (
    _cst_weekday_set,
    generate_chapter_plan,
    resolve_cst_syllabus_context,
)
from dars.breakdown.planner_llm import PlannerLLMError
from dars.breakdown.class_chapter_service import (
    list_class_path,
    seed_class_chapters_from_breakdown,
)
from dars.breakdown.mark_taught_service import (
    mark_assessment_slot,
    mark_lesson_slot,
)
from dars.breakdown.onboarding_service import onboard_cst
from dars.breakdown.projector import project_cst_schedule
from dars.breakdown.reteach_service import (
    RETEACH_MASTERY_THRESHOLD,
    reteach,
    suggest_reteach,
)
from dars.v2_api.deps import OrgContext, get_current_org, get_db_conn
from dars.v2_api.schemas_class_actions import (
    ClassAssessmentSlotListItem,
    ClassAssessmentSlotListResponse,
    ClassLessonSlotListItem,
    ClassLessonSlotListResponse,
    ClassPathChapter,
    CompleteAssessmentBody,
    CstTimelineResponse,
    GenerateChapterPlanResponse,
    MarkActionResponse,
    MarkTaughtBody,
    OnboardBody,
    OnboardResponse,
    OverflowConsequencePayload,
    ReteachActionBody,
    ReteachActionResponse,
    ReteachSuggestionItem,
    ReteachSuggestionResponse,
    SkipBody,
    SubSLOCoverageEntry,
    SubSLOCoverageResponse,
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

        # F-1.4 (dynamic-chapter-planner): surface the projector's existing
        # overflow flag as a count. No new projection — just tally the items.
        overflow_count = sum(1 for i in items if i.is_overflow)

        log.info(
            "get_cst_timeline: exit cst=%s items=%d overflow=%d conflicts=%d",
            cst_id, len(items), overflow_count,
            sum(1 for i in items if i.is_conflict),
        )
        return CstTimelineResponse(
            cst_id=cst_id, items=items, overflow_count=overflow_count
        )
    except HTTPException:
        raise
    except Exception:
        log.error("get_cst_timeline: failed cst=%s", cst_id, exc_info=True)
        raise


# ---------------------------------------------------------------------------
# Teacher Chapter Plan — syllabus view + break-it-down (Phase 3)
# ---------------------------------------------------------------------------


def _path_chapter(row: dict) -> ClassPathChapter:
    """Map a `list_class_path` row dict to the response schema."""
    return ClassPathChapter(
        book_chapter_id=row["book_chapter_id"],
        chapter_number=row["chapter_number"],
        title=row["title"],
        position=row["position"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        slot_count=row["slot_count"],
        status=row["status"],
    )


async def _build_syllabus_response(
    conn: asyncpg.Connection, cst_id: UUID
) -> SyllabusForCstResponse:
    """Shared assembly: the read-only class path (mirrored from the org
    breakdown) + periods/week."""
    ctx = await resolve_cst_syllabus_context(conn, cst_id)
    weekdays = await _cst_weekday_set(conn, cst_id)
    path = await list_class_path(conn, cst_id)
    return SyllabusForCstResponse(
        cst_id=cst_id,
        syllabus_breakdown_id=ctx.syllabus_breakdown_id,
        periods_per_week=len(weekdays),
        chapters=[_path_chapter(r) for r in path],
    )


@router.get("/csts/{cst_id}/syllabus", response_model=SyllabusForCstResponse)
async def get_cst_syllabus(
    cst_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SyllabusForCstResponse:
    """The class's read-only teaching path (`class_chapters`), auto-seeded from
    the org's published Syllabus Breakdown on first read (D-2). Each chapter
    carries the org-decided dates, slot count and derived status (D-4), plus the
    class's periods/week. No published breakdown → empty path (D-7)."""
    log.info("get_cst_syllabus: entry cst=%s", cst_id)
    await _ensure_cst_in_org(conn, cst_id, org.id)
    # First read materialises the path from the org breakdown (idempotent).
    await seed_class_chapters_from_breakdown(conn, cst_id)
    resp = await _build_syllabus_response(conn, cst_id)
    log.info(
        "get_cst_syllabus: exit cst=%s chapters=%d periods/wk=%d",
        cst_id, len(resp.chapters), resp.periods_per_week,
    )
    return resp


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
    except PlannerLLMError as e:
        # D-5: planner transport failure — surface as 502, no fallback.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"planner LLM error: {e}",
        )
    except ValueError as e:
        # Covers refusals + PlanParseError / PlanValidationError (D-5).
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
        flex_slot_count=result.flex_slot_count,
        warnings=result.warnings,
    )


# ---------------------------------------------------------------------------
# Reteach trigger (dynamic-chapter-planner Phase 3, F-3.1/F-3.2/F-3.3, D-9)
#
# A graded FA slot whose per-sub-SLO mastery is below the threshold surfaces a
# suggestion (GET, read-only); the teacher then confirms an explicit
# lightweight|heavy action (POST). Reteach is NEVER auto-applied (D-9).
# ---------------------------------------------------------------------------


async def _ensure_assessment_slot_cst_in_org(
    conn: asyncpg.Connection, class_assessment_slot_id: UUID, org_id: UUID
) -> None:
    """404 unless the FA slot exists and belongs to the calling org (no 403 leak
    of cross-org slot ids — mirrors the other tenancy guards)."""
    row = await conn.fetchrow(
        "SELECT org_id FROM class_assessment_slots WHERE id = $1",
        class_assessment_slot_id,
    )
    if row is None or row["org_id"] != org_id:
        raise HTTPException(status_code=404, detail="assessment slot not found")


@router.get(
    "/class-assessment-slots/{class_assessment_slot_id}/reteach-suggestion",
    response_model=ReteachSuggestionResponse,
)
async def get_reteach_suggestion(
    class_assessment_slot_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> ReteachSuggestionResponse:
    """F-3.1: the below-threshold sub-SLOs for a graded FA slot — the teacher-app
    badge payload. Read only; empty list ⇒ no badge. Reteach never auto-applies
    (D-9): acting on a suggestion requires the explicit POST below."""
    log.info(
        "get_reteach_suggestion: entry slot=%s", class_assessment_slot_id
    )
    await _ensure_assessment_slot_cst_in_org(conn, class_assessment_slot_id, org.id)
    try:
        suggestions = await suggest_reteach(conn, class_assessment_slot_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    log.info(
        "get_reteach_suggestion: exit slot=%s below_threshold=%d",
        class_assessment_slot_id, len(suggestions),
    )
    return ReteachSuggestionResponse(
        class_assessment_slot_id=class_assessment_slot_id,
        threshold=RETEACH_MASTERY_THRESHOLD,
        items=[
            ReteachSuggestionItem(
                sub_slo_id=s.sub_slo_id,
                sub_slo_code=s.sub_slo_code,
                statement=s.statement,
                mastery_percent=s.mastery_percent,
            )
            for s in suggestions
        ],
    )


@router.post(
    "/class-assessment-slots/{class_assessment_slot_id}/reteach",
    response_model=ReteachActionResponse,
)
async def confirm_reteach(
    class_assessment_slot_id: UUID,
    body: ReteachActionBody,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> ReteachActionResponse:
    """F-3.2/F-3.3: apply a teacher-confirmed reteach for one sub-SLO. The
    teacher's explicit `mode` decides the path — there is NO auto-apply (D-9):

      lightweight (default): flip coverage to needs-rework; no slot, no shift.
      heavy: consume the nearest downstream flex slot (no shift), else insert a
             new lesson slot (shifts the tail) and report the overflow
             consequence (D-17). The reteach slot rides the on-demand LP path
             (lp_type='revision', origin='reteach') — D-10.
    """
    log.info(
        "confirm_reteach: entry slot=%s sub_slo=%s mode=%s",
        class_assessment_slot_id, body.sub_slo_id, body.mode,
    )
    await _ensure_assessment_slot_cst_in_org(conn, class_assessment_slot_id, org.id)
    try:
        result = await reteach(
            conn,
            class_assessment_slot_id=class_assessment_slot_id,
            sub_slo_id=body.sub_slo_id,
            mode=body.mode,
        )
    except ValueError as e:
        # Bad mode, non-FA slot, unresolvable reteach topic, or a taught-lock
        # refusal from the mutation primitives → caller-fixable, 422.
        raise HTTPException(status_code=422, detail=str(e))

    consequence = None
    if result.consequence is not None:
        consequence = OverflowConsequencePayload(
            overflow_before=result.consequence.overflow_before,
            overflow_after=result.consequence.overflow_after,
            newly_overflowed_positions=result.consequence.newly_overflowed_positions,
            first_overflow_position=result.consequence.first_overflow_position,
        )
    log.info(
        "confirm_reteach: exit slot=%s sub_slo=%s path=%s reteach_slot=%s",
        class_assessment_slot_id, body.sub_slo_id, result.path, result.slot_id,
    )
    return ReteachActionResponse(
        class_assessment_slot_id=class_assessment_slot_id,
        sub_slo_id=body.sub_slo_id,
        path=result.path,
        reteach_slot_id=result.slot_id,
        consequence=consequence,
    )
