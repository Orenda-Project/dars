"""
F2.15 + F2.16 — /today and /me/calendar.

Both endpoints use the same F2.8 projector so they cannot disagree
about which slot lands on which date.

Auth: X-API-Key (per-org). Targets each CST owned by the org's
default_teacher_id, in arbitrary order. Empty list if the teacher has
no CSTs or the projector returns nothing for today's week.
"""
import logging
from datetime import date, timedelta
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from dars.breakdown.projector import (
    ProjectedSlot,
    project_cst_schedule,
)
from dars.v2_api.deps import OrgContext, get_current_org, get_db_conn
from dars.v2_api.schemas_today_calendar import (
    AssessmentSlotEntry,
    CalendarCSTSchedule,
    CalendarDay,
    CalendarResponse,
    LessonSlotEntry,
    PreviousTaughtSummary,
    TodayEntry,
    TodayResponse,
)

log = logging.getLogger("v2_api.today_calendar")

router = APIRouter(prefix="/api/v2", tags=["v2-today-calendar"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _csts_for_teacher(
    conn: asyncpg.Connection, org_id: UUID, teacher_id: UUID
) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        SELECT
            cst.id AS cst_id,
            cst.subject_id,
            s.code AS subject_code,
            sc.grade_id,
            g.code AS grade_code
        FROM class_subject_teachers cst
        JOIN school_classes sc ON sc.id = cst.school_class_id
        JOIN subjects s ON s.id = cst.subject_id
        JOIN grades g ON g.id = sc.grade_id
        WHERE cst.org_id = $1 AND cst.teacher_id = $2
        """,
        org_id, teacher_id,
    )


async def _load_lesson_slot_full(
    conn: asyncpg.Connection, slot_id: UUID
) -> LessonSlotEntry | None:
    row = await conn.fetchrow(
        """
        SELECT id, position, slot_type, lp_type, topic_id, status, anchor_date
        FROM class_lesson_slots WHERE id = $1
        """,
        slot_id,
    )
    if row is None:
        return None
    return LessonSlotEntry(
        slot_id=row["id"],
        position=row["position"],
        slot_type=row["slot_type"],
        lp_type=row["lp_type"],
        topic_id=row["topic_id"],
        status=row["status"],
        anchor_date=row["anchor_date"],
    )


async def _load_assessment_slot_full(
    conn: asyncpg.Connection, slot_id: UUID
) -> AssessmentSlotEntry | None:
    row = await conn.fetchrow(
        """
        SELECT id, position, assessment_type, status, anchor_date
        FROM class_assessment_slots WHERE id = $1
        """,
        slot_id,
    )
    if row is None:
        return None
    topic_rows = await conn.fetch(
        """
        SELECT topic_id
        FROM class_assessment_slot_topics
        WHERE class_assessment_slot_id = $1
        ORDER BY position
        """,
        slot_id,
    )
    return AssessmentSlotEntry(
        slot_id=row["id"],
        position=row["position"],
        assessment_type=row["assessment_type"],
        status=row["status"],
        anchor_date=row["anchor_date"],
        topic_ids=[r["topic_id"] for r in topic_rows],
    )


async def _previous_taught_summary(
    conn: asyncpg.Connection, cst_id: UUID, before_position: int
) -> PreviousTaughtSummary | None:
    row = await conn.fetchrow(
        """
        SELECT s.id, s.position, s.topic_id, MAX(sp.occurred_on) AS taught_on
        FROM slot_progress sp
        JOIN class_lesson_slots s ON s.id = sp.slot_id
        WHERE sp.cst_id = $1
          AND sp.slot_kind = 'lesson'
          AND sp.action = 'taught'
          AND s.position < $2
        GROUP BY s.id, s.position, s.topic_id
        ORDER BY s.position DESC
        LIMIT 1
        """,
        cst_id, before_position,
    )
    if row is None:
        return None
    return PreviousTaughtSummary(
        slot_id=row["id"],
        position=row["position"],
        topic_id=row["topic_id"],
        taught_on=row["taught_on"],
    )


# ---------------------------------------------------------------------------
# F2.15 — /today
# ---------------------------------------------------------------------------


@router.get("/today", response_model=TodayResponse)
async def today(
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
    as_of: date | None = Query(default=None, description="Override 'today' for testing"),
) -> TodayResponse:
    today_date = as_of or date.today()
    if org.default_teacher_id is None:
        return TodayResponse(items=[], as_of=today_date)

    csts = await _csts_for_teacher(conn, org.id, org.default_teacher_id)
    items: list[TodayEntry] = []
    for cst in csts:
        projected = await project_cst_schedule(conn, cst["cst_id"])
        match: ProjectedSlot | None = None
        for p in projected:
            if p.projected_date == today_date:
                match = p
                break
        if match is None:
            continue

        entry = TodayEntry(
            cst_id=cst["cst_id"],
            subject_id=cst["subject_id"],
            subject_code=cst["subject_code"],
            grade_id=cst["grade_id"],
            grade_code=cst["grade_code"],
            day_number=match.position,
            is_conflict=match.is_conflict,
            is_overflow=match.is_overflow,
        )
        if match.slot_kind == "lesson":
            entry.lesson_slot = await _load_lesson_slot_full(conn, match.slot_id)
        else:
            entry.assessment_slot = await _load_assessment_slot_full(conn, match.slot_id)
        entry.previous_taught = await _previous_taught_summary(
            conn, cst["cst_id"], match.position
        )
        items.append(entry)

    return TodayResponse(items=items, as_of=today_date)


# ---------------------------------------------------------------------------
# F2.16 — /me/calendar
# ---------------------------------------------------------------------------


@router.get("/me/calendar", response_model=CalendarResponse)
async def my_calendar(
    week_start: date = Query(description="ISO date (YYYY-MM-DD). Treated as the first day of the calendar window."),
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> CalendarResponse:
    if org.default_teacher_id is None:
        return CalendarResponse(
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            csts=[],
        )

    week_end = week_start + timedelta(days=6)
    window: list[date] = [week_start + timedelta(days=i) for i in range(7)]

    csts = await _csts_for_teacher(conn, org.id, org.default_teacher_id)
    schedules: list[CalendarCSTSchedule] = []
    for cst in csts:
        projected = await project_cst_schedule(conn, cst["cst_id"])
        by_date: dict[date, list[ProjectedSlot]] = {}
        for p in projected:
            if p.projected_date and week_start <= p.projected_date <= week_end:
                by_date.setdefault(p.projected_date, []).append(p)

        days: list[CalendarDay] = []
        for d in window:
            lesson_entries: list[LessonSlotEntry] = []
            assess_entries: list[AssessmentSlotEntry] = []
            for p in by_date.get(d, []):
                if p.slot_kind == "lesson":
                    e = await _load_lesson_slot_full(conn, p.slot_id)
                    if e is not None:
                        lesson_entries.append(e)
                else:
                    e = await _load_assessment_slot_full(conn, p.slot_id)
                    if e is not None:
                        assess_entries.append(e)
            days.append(CalendarDay(
                day=d,
                lesson_slots=lesson_entries,
                assessment_slots=assess_entries,
            ))
        schedules.append(CalendarCSTSchedule(
            cst_id=cst["cst_id"],
            subject_id=cst["subject_id"],
            subject_code=cst["subject_code"],
            grade_id=cst["grade_id"],
            grade_code=cst["grade_code"],
            days=days,
        ))

    return CalendarResponse(week_start=week_start, week_end=week_end, csts=schedules)
