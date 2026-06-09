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
from fastapi import APIRouter, Depends, Query

from dars.breakdown.chapter_plan_service import generate_chapter_plan
from dars.breakdown.class_chapter_service import (
    STATUS_DONE,
    list_class_path,
    seed_class_chapters_from_breakdown,
)
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
    CurrentChapterSummary,
    LessonSlotEntry,
    NextUpSummary,
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


async def _next_up_summary(
    conn: asyncpg.Connection, cst_id: UUID, after_position: int
) -> NextUpSummary | None:
    """
    The next lesson slot after `after_position` (by global position) for this
    CST — symmetric to `_previous_taught_summary`. Returns None at end of course.

    Looks at planned lesson slots only (mirrors previous_taught's lesson scope);
    `projected_date` is left None here and filled in by the caller from the
    already-computed projection (the projector is the single source of dates).
    """
    row = await conn.fetchrow(
        """
        SELECT id, position, topic_id, lp_type
        FROM class_lesson_slots
        WHERE cst_id = $1 AND position > $2
        ORDER BY position
        LIMIT 1
        """,
        cst_id, after_position,
    )
    if row is None:
        return None
    return NextUpSummary(
        slot_id=row["id"],
        position=row["position"],
        topic_id=row["topic_id"],
        lp_type=row["lp_type"],
        projected_date=None,
    )


async def _is_generated_set(conn: asyncpg.Connection, cst_id: UUID) -> set[UUID]:
    """book_chapter_ids that already have generated lesson slots for this CST.

    Snapshotted before auto-plan so the endpoint can count how many chapters it
    actually broke down this request (logging only)."""
    rows = await conn.fetch(
        """
        SELECT DISTINCT book_chapter_id
        FROM class_lesson_slots
        WHERE cst_id = $1 AND book_chapter_id IS NOT NULL
        """,
        cst_id,
    )
    return {r["book_chapter_id"] for r in rows}


async def _ensure_path_and_current_chapter(
    conn: asyncpg.Connection, org: OrgContext, cst_id: UUID
) -> dict | None:
    """
    Seed the class path from the org breakdown (idempotent) and resolve the
    "current chapter" = the first chapter by position whose derived status is
    not 'done'. If that chapter has no generated slots yet but has a valid date
    range, lazily auto-break-it-down so /today can show prev/today/next.

    Returns the current-chapter dict (book_chapter_id, chapter_number, title,
    status, slot_count, is_generated) from the refreshed path, or None when the
    CST has no path (no published org breakdown) or the whole path is done.

    Auto-plan is best-effort: a ValueError (already broken down by a concurrent
    request / not in path / no dates) is logged at INFO and swallowed — those
    are benign. Planner failures (PlannerLLMError / parse / validation) are NOT
    caught here (D-5): they propagate so /today surfaces the real error.
    """
    # Idempotent: no-ops when the path already exists or no breakdown is published.
    await seed_class_chapters_from_breakdown(conn, cst_id)

    path = await list_class_path(conn, cst_id)
    if not path:
        log.info("today.ensure_path: cst=%s has no class path — skipping", cst_id)
        return None

    current = next((c for c in path if c["status"] != STATUS_DONE), None)
    if current is None:
        # Whole path done — no current chapter, but the caller still emits an
        # entry (previous_taught / course-complete state).
        log.info("today.ensure_path: cst=%s path fully done", cst_id)
        return None

    # Lazily break down the current chapter on first load (the teacher-demo
    # gap: no slots → empty Today). Guarded so we don't call the planner when
    # it's already broken down or has no dates set.
    if not current["is_generated"] and current["slot_count"] > 0:
        log.info(
            "today.ensure_path: auto-planning current chapter cst=%s chapter=%s",
            cst_id, current["book_chapter_id"],
        )
        try:
            result = await generate_chapter_plan(
                conn,
                cst_id=cst_id,
                book_chapter_id=current["book_chapter_id"],
                org_id=org.id,
            )
            log.info(
                "today.ensure_path: auto-planned cst=%s chapter=%s lessons=%d",
                cst_id, current["book_chapter_id"], result.lesson_slot_count,
            )
            # Refresh: status/is_generated changed; re-pick the current chapter
            # (it may now be in_progress but is still the current one).
            path = await list_class_path(conn, cst_id)
            current = next(
                (c for c in path if c["status"] != STATUS_DONE), current
            )
        except ValueError as exc:
            # Benign: already broken down (concurrent request), not in path, or
            # no date range. Leave the chapter as-is; the projector handles it.
            log.info(
                "today.ensure_path: auto-plan skipped cst=%s chapter=%s — %s",
                cst_id, current["book_chapter_id"], exc,
            )

    return current


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
    log.info(
        "today: entry org=%s teacher=%s as_of=%s",
        org.id, org.default_teacher_id, today_date,
    )
    if org.default_teacher_id is None:
        log.info("today: exit org=%s no default_teacher_id — 0 items", org.id)
        return TodayResponse(items=[], as_of=today_date)

    csts = await _csts_for_teacher(conn, org.id, org.default_teacher_id)
    items: list[TodayEntry] = []
    auto_planned = 0
    for cst in csts:
        cst_id = cst["cst_id"]

        # Teacher-demo gap (today-prev-current-next): seed the org-decided path
        # and lazily break down the current chapter so Today is useful even when
        # the teacher hasn't broken anything down. None ⇒ no path / path done.
        before = await _is_generated_set(conn, cst_id)
        current_chapter = await _ensure_path_and_current_chapter(conn, org, cst_id)
        if current_chapter is not None and current_chapter["book_chapter_id"] not in before:
            auto_planned += 1

        projected = await project_cst_schedule(conn, cst_id)
        # position → projected_date, so prev/today/next carry their dates.
        date_by_pos: dict[int, date | None] = {
            p.position: p.projected_date for p in projected
        }
        match: ProjectedSlot | None = next(
            (p for p in projected if p.projected_date == today_date), None
        )

        # No teaching today AND no path to anchor against → skip (nothing to
        # show). A planned/seeded path always yields a current_chapter, so we
        # still emit an entry below (prev / next / "no class today").
        if match is None and current_chapter is None:
            continue

        entry = TodayEntry(
            cst_id=cst_id,
            subject_id=cst["subject_id"],
            subject_code=cst["subject_code"],
            grade_id=cst["grade_id"],
            grade_code=cst["grade_code"],
            day_number=match.position if match else None,
            is_conflict=match.is_conflict if match else False,
            is_overflow=match.is_overflow if match else False,
        )

        if current_chapter is not None:
            entry.current_chapter = CurrentChapterSummary(
                book_chapter_id=current_chapter["book_chapter_id"],
                chapter_number=current_chapter["chapter_number"],
                title=current_chapter["title"],
                status=current_chapter["status"],
            )

        # Anchor position for prev/next. On a teaching day it's today's slot;
        # otherwise it's the last slot whose projected date is on/before today
        # (0 when today precedes the course), so prev/next bracket "where you are".
        if match is not None:
            anchor_position = match.position
            if match.slot_kind == "lesson":
                entry.lesson_slot = await _load_lesson_slot_full(conn, match.slot_id)
            else:
                entry.assessment_slot = await _load_assessment_slot_full(conn, match.slot_id)
            prev_before = anchor_position       # taught strictly before today
            next_after = anchor_position        # next strictly after today
        else:
            past = [
                p.position for p in projected
                if p.projected_date is not None and p.projected_date <= today_date
            ]
            anchor_position = max(past) if past else 0
            prev_before = anchor_position + 1   # include a slot taught on the anchor
            next_after = anchor_position        # next future slot

        entry.previous_taught = await _previous_taught_summary(
            conn, cst_id, prev_before
        )
        entry.next_up = await _next_up_summary(conn, cst_id, next_after)
        if entry.next_up is not None:
            entry.next_up.projected_date = date_by_pos.get(entry.next_up.position)
        items.append(entry)

    log.info(
        "today: exit org=%s items=%d auto_planned=%d", org.id, len(items), auto_planned
    )
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
