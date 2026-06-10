"""
Syllabus-breakdown CRUD endpoints (Phase 2, global-only).

Auth: all endpoints take get_current_org (X-API-Key OR X-Admin-Session).
Syllabus breakdowns are GLOBAL: there is no org/class scope, no forks, and
no per-class slots. Any authenticated org may read/create/edit/delete.

Published breakdowns are immutable (PATCH/DELETE on chapters → 409, PATCH on
the breakdown itself → 409). Publish flips status: 'draft' → 'published'.
Delete on a draft is soft (status='deleted'); delete on a published is 409.
"""
import logging
from datetime import date
from uuid import UUID

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from dars.breakdown.chapter_calendar import (
    compute_range_warnings,
    derived_teaching_days,
    expand_ranges,
)
from dars.breakdown.slo_breakdown_service import (
    SUBJECT_CODE_TO_KEY,
    run_breakdown_for_slos,
)
from dars.v2_api.deps import (
    OrgContext,
    get_current_org,
    get_db_conn,
    get_db_pool,
)
from dars.v2_api.schemas_syllabus import (
    DateRangeCreate,
    DateRangeRead,
    DateRangeUpdate,
    SubSLOBreakdownResponse,
    SubSLOBulkAccepted,
    SubSLOBulkRequest,
    SyllabusBreakdownCreate,
    SyllabusBreakdownListItem,
    SyllabusBreakdownListResponse,
    SyllabusBreakdownRead,
    SyllabusBreakdownUpdate,
    SyllabusChapterCreate,
    SyllabusChapterRead,
    SyllabusChapterUpdate,
)

log = logging.getLogger("v2_api.syllabus")

router = APIRouter(
    prefix="/api/v2",
    tags=["v2-syllabus"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_breakdown_or_404(
    conn: asyncpg.Connection, breakdown_id: UUID
) -> asyncpg.Record:
    row = await conn.fetchrow(
        """
        SELECT id, curriculum_id, grade_id, subject_id, book_id, status,
               created_at, updated_at
        FROM syllabus_breakdowns
        WHERE id = $1
        """,
        breakdown_id,
    )
    if row is None or row["status"] == "deleted":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Syllabus breakdown not found",
        )
    return row


async def _require_draft(
    conn: asyncpg.Connection, breakdown_id: UUID
) -> asyncpg.Record:
    row = await _load_breakdown_or_404(conn, breakdown_id)
    if row["status"] != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Syllabus breakdown is {row['status']}; only drafts can be modified",
        )
    return row


async def _validate_chapter_belongs_to_breakdown(
    conn: asyncpg.Connection, breakdown_id: UUID, chapter_id: UUID
) -> asyncpg.Record:
    row = await conn.fetchrow(
        """
        SELECT id, syllabus_breakdown_id, book_chapter_id, position,
               start_date, end_date
        FROM syllabus_chapters
        WHERE id = $1 AND syllabus_breakdown_id = $2
        """,
        chapter_id, breakdown_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chapter not found on this syllabus breakdown",
        )
    return row


# Map the two range kinds to their tables. Both share the identical shape
# (id, syllabus_breakdown_id, start_date, end_date, name, created_at) so one
# set of helpers and endpoint bodies serves both (D-1/D-14).
_RANGE_TABLES = {
    "exam-periods": "exam_periods",
    "holidays": "breakdown_holidays",
}


async def _fetch_ranges(
    conn: asyncpg.Connection, table: str, breakdown_id: UUID
) -> list[asyncpg.Record]:
    """All rows of a range table for a breakdown, oldest-first (stable order)."""
    return await conn.fetch(
        f"""
        SELECT id, syllabus_breakdown_id, start_date, end_date, name, created_at
        FROM {table}
        WHERE syllabus_breakdown_id = $1
        ORDER BY start_date, created_at
        """,
        breakdown_id,
    )


async def _validate_range_belongs(
    conn: asyncpg.Connection, table: str, breakdown_id: UUID, range_id: UUID
) -> asyncpg.Record:
    """404 unless `range_id` is a row of `table` on this breakdown."""
    row = await conn.fetchrow(
        f"""
        SELECT id, syllabus_breakdown_id, start_date, end_date, name, created_at
        FROM {table}
        WHERE id = $1 AND syllabus_breakdown_id = $2
        """,
        range_id, breakdown_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Date range not found on this syllabus breakdown",
        )
    return row


def _reject_inverted_range(start_date: date, end_date: date) -> None:
    """422 when end_date < start_date (advisory-uniform with chapters, D-4)."""
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be on or after start_date",
        )


async def _hydrate_breakdown(
    conn: asyncpg.Connection, row: asyncpg.Record
) -> SyllabusBreakdownRead:
    chapters = await conn.fetch(
        """
        SELECT id, syllabus_breakdown_id, book_chapter_id, position,
               start_date, end_date
        FROM syllabus_chapters
        WHERE syllabus_breakdown_id = $1
        ORDER BY position
        """,
        row["id"],
    )

    # F-1.3 (D-2/D-4): the breakdown's own exam-period + holiday dates are the
    # exclusion set for admin-side teaching-day derivation. A chapter range
    # fully inside an exam/holiday window naturally surfaces a
    # zero_teaching_days warning via compute_range_warnings. Global breakdowns
    # have no org/school/CST calendar, so this is the only holiday source here.
    exam_periods = await _fetch_ranges(conn, "exam_periods", row["id"])
    holiday_ranges = await _fetch_ranges(conn, "breakdown_holidays", row["id"])
    holidays = expand_ranges(exam_periods) | expand_ranges(holiday_ranges)

    chapter_dicts = [dict(c) for c in chapters]
    for c in chapter_dicts:
        c["derived_teaching_days"] = derived_teaching_days(
            c["start_date"], c["end_date"], holidays
        )
    warnings = compute_range_warnings(chapter_dicts, holidays)

    return SyllabusBreakdownRead(
        **dict(row),
        chapters=[SyllabusChapterRead(**c) for c in chapter_dicts],
        chapter_range_warnings=warnings,
        exam_periods=[DateRangeRead(**dict(r)) for r in exam_periods],
        holidays=[DateRangeRead(**dict(r)) for r in holiday_ranges],
    )


# ---------------------------------------------------------------------------
# Syllabus breakdown CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/syllabus-breakdowns",
    response_model=SyllabusBreakdownRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_breakdown(
    payload: SyllabusBreakdownCreate,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SyllabusBreakdownRead:
    log.info(
        "create_syllabus_breakdown: org=%s subject_id=%s book_id=%s",
        org.id, payload.subject_id, payload.book_id,
    )
    row = await conn.fetchrow(
        """
        INSERT INTO syllabus_breakdowns
            (curriculum_id, grade_id, subject_id, book_id, status)
        VALUES ($1, $2, $3, $4, 'draft')
        RETURNING id, curriculum_id, grade_id, subject_id, book_id, status,
                  created_at, updated_at
        """,
        payload.curriculum_id, payload.grade_id, payload.subject_id, payload.book_id,
    )
    log.info("create_syllabus_breakdown: created id=%s", row["id"])
    return await _hydrate_breakdown(conn, row)


@router.get("/syllabus-breakdowns", response_model=SyllabusBreakdownListResponse)
async def list_breakdowns(
    curriculum_id: UUID | None = Query(default=None),
    grade_id: UUID | None = Query(default=None),
    subject_id: UUID | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    _org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SyllabusBreakdownListResponse:
    params: list = []
    where: list[str] = ["status != 'deleted'"]
    if curriculum_id is not None:
        params.append(curriculum_id)
        where.append(f"curriculum_id = ${len(params)}")
    if grade_id is not None:
        params.append(grade_id)
        where.append(f"grade_id = ${len(params)}")
    if subject_id is not None:
        params.append(subject_id)
        where.append(f"subject_id = ${len(params)}")
    if status_ is not None:
        params.append(status_)
        where.append(f"status = ${len(params)}")
    where_sql = "WHERE " + " AND ".join(where)
    rows = await conn.fetch(
        f"""
        SELECT id, curriculum_id, grade_id, subject_id, book_id, status,
               created_at, updated_at
        FROM syllabus_breakdowns
        {where_sql}
        ORDER BY created_at DESC
        """,
        *params,
    )
    return SyllabusBreakdownListResponse(
        items=[SyllabusBreakdownListItem(**dict(r)) for r in rows]
    )


@router.get(
    "/syllabus-breakdowns/{breakdown_id}", response_model=SyllabusBreakdownRead
)
async def get_breakdown(
    breakdown_id: UUID,
    _org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SyllabusBreakdownRead:
    row = await _load_breakdown_or_404(conn, breakdown_id)
    return await _hydrate_breakdown(conn, row)


@router.patch(
    "/syllabus-breakdowns/{breakdown_id}", response_model=SyllabusBreakdownRead
)
async def update_breakdown(
    breakdown_id: UUID,
    payload: SyllabusBreakdownUpdate,
    _org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SyllabusBreakdownRead:
    current = await _load_breakdown_or_404(conn, breakdown_id)
    if current["status"] != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Syllabus breakdown status={current['status']!r} cannot be modified",
        )

    if payload.book_id is None:
        return await _hydrate_breakdown(conn, current)
    row = await conn.fetchrow(
        """
        UPDATE syllabus_breakdowns
        SET book_id = $1, updated_at = now()
        WHERE id = $2
        RETURNING id, curriculum_id, grade_id, subject_id, book_id, status,
                  created_at, updated_at
        """,
        payload.book_id, breakdown_id,
    )
    return await _hydrate_breakdown(conn, row)


@router.post(
    "/syllabus-breakdowns/{breakdown_id}/publish",
    response_model=SyllabusBreakdownRead,
)
async def publish_breakdown(
    breakdown_id: UUID,
    _org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SyllabusBreakdownRead:
    # Publishing a Syllabus Breakdown only flips its status. Generation no
    # longer fires on publish — slots are generated teacher-side from the
    # class's Chapter Plan (syllabus-breakdown-and-teacher-chapter-plan D-5).
    current = await _require_draft(conn, breakdown_id)

    # A published syllabus must be teacher-usable: it needs at least one
    # chapter, and every chapter must have a full date range (the teacher
    # "break it down" flow derives slot counts from these dates).
    undated = await conn.fetchval(
        """
        SELECT count(*) FROM syllabus_chapters
        WHERE syllabus_breakdown_id = $1
          AND (start_date IS NULL OR end_date IS NULL)
        """,
        current["id"],
    )
    total = await conn.fetchval(
        "SELECT count(*) FROM syllabus_chapters WHERE syllabus_breakdown_id = $1",
        current["id"],
    )
    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="cannot publish a syllabus breakdown with no chapters",
        )
    if undated:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"cannot publish: {undated} chapter(s) have no date range — "
                "set start and end dates for every chapter first"
            ),
        )

    row = await conn.fetchrow(
        """
        UPDATE syllabus_breakdowns
        SET status = 'published', updated_at = now()
        WHERE id = $1
        RETURNING id, curriculum_id, grade_id, subject_id, book_id, status,
                  created_at, updated_at
        """,
        current["id"],
    )
    log.info("publish_syllabus_breakdown: id=%s now published", breakdown_id)
    return await _hydrate_breakdown(conn, row)


@router.delete(
    "/syllabus-breakdowns/{breakdown_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_breakdown(
    breakdown_id: UUID,
    _org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> None:
    current = await _load_breakdown_or_404(conn, breakdown_id)
    if current["status"] == "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a published syllabus breakdown",
        )
    await conn.execute(
        "UPDATE syllabus_breakdowns SET status = 'deleted', updated_at = now() WHERE id = $1",
        breakdown_id,
    )
    log.info("delete_syllabus_breakdown: soft-deleted id=%s", breakdown_id)


# ---------------------------------------------------------------------------
# Chapters
# ---------------------------------------------------------------------------


@router.post(
    "/syllabus-breakdowns/{breakdown_id}/chapters",
    response_model=SyllabusChapterRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_chapter(
    breakdown_id: UUID,
    payload: SyllabusChapterCreate,
    _org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SyllabusChapterRead:
    await _require_draft(conn, breakdown_id)
    exists = await conn.fetchval(
        "SELECT 1 FROM book_chapters WHERE id = $1", payload.book_chapter_id
    )
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"book_chapter_id {payload.book_chapter_id} not found",
        )
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO syllabus_chapters
                (syllabus_breakdown_id, book_chapter_id, position, start_date, end_date)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, syllabus_breakdown_id, book_chapter_id, position,
                      start_date, end_date
            """,
            breakdown_id, payload.book_chapter_id, payload.position,
            payload.start_date, payload.end_date,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"position {payload.position} is already taken on this syllabus breakdown",
        )
    return SyllabusChapterRead(**dict(row))


@router.patch(
    "/syllabus-breakdowns/{breakdown_id}/chapters/{chapter_id}",
    response_model=SyllabusChapterRead,
)
async def update_chapter(
    breakdown_id: UUID,
    chapter_id: UUID,
    payload: SyllabusChapterUpdate,
    _org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SyllabusChapterRead:
    await _require_draft(conn, breakdown_id)
    await _validate_chapter_belongs_to_breakdown(conn, breakdown_id, chapter_id)
    sets: list[str] = []
    params: list = []
    if payload.position is not None:
        params.append(payload.position)
        sets.append(f"position = ${len(params)}")
    # D-8: None means "omit"; clearing a date range is not supported here.
    if payload.start_date is not None:
        params.append(payload.start_date)
        sets.append(f"start_date = ${len(params)}")
    if payload.end_date is not None:
        params.append(payload.end_date)
        sets.append(f"end_date = ${len(params)}")
    if not sets:
        row = await conn.fetchrow(
            "SELECT id, syllabus_breakdown_id, book_chapter_id, position, "
            "start_date, end_date FROM syllabus_chapters WHERE id = $1",
            chapter_id,
        )
        return SyllabusChapterRead(**dict(row))
    params.append(chapter_id)
    try:
        row = await conn.fetchrow(
            f"""
            UPDATE syllabus_chapters
            SET {", ".join(sets)}
            WHERE id = ${len(params)}
            RETURNING id, syllabus_breakdown_id, book_chapter_id, position,
                      start_date, end_date
            """,
            *params,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="position conflict on this syllabus breakdown",
        )
    return SyllabusChapterRead(**dict(row))


@router.delete(
    "/syllabus-breakdowns/{breakdown_id}/chapters/{chapter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_chapter(
    breakdown_id: UUID,
    chapter_id: UUID,
    _org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> None:
    await _require_draft(conn, breakdown_id)
    await _validate_chapter_belongs_to_breakdown(conn, breakdown_id, chapter_id)
    await conn.execute(
        "DELETE FROM syllabus_chapters WHERE id = $1", chapter_id
    )
    log.info("delete_syllabus_chapter: deleted id=%s", chapter_id)


# ---------------------------------------------------------------------------
# Exam periods + breakdown holidays (F-1.5 — D-1/D-5/D-14)
#
# exam_periods and breakdown_holidays share an identical shape, so create /
# update / delete bodies are shared. Mutations are publish-locked (D-5) via
# _require_draft (409 if the breakdown isn't a draft); end_date < start_date
# is rejected 422 (D-4). Reads reach these rows only THROUGH the breakdown,
# which is itself tenant-scoped (the breakdown 404 gate runs first).
# ---------------------------------------------------------------------------


async def _create_range(
    conn: asyncpg.Connection,
    table: str,
    breakdown_id: UUID,
    payload: DateRangeCreate,
) -> DateRangeRead:
    log.info(
        "create_breakdown_range: entry table=%s breakdown=%s start=%s end=%s name=%r",
        table, breakdown_id, payload.start_date, payload.end_date, payload.name,
    )
    try:
        await _require_draft(conn, breakdown_id)
        _reject_inverted_range(payload.start_date, payload.end_date)
        row = await conn.fetchrow(
            f"""
            INSERT INTO {table} (syllabus_breakdown_id, start_date, end_date, name)
            VALUES ($1, $2, $3, $4)
            RETURNING id, syllabus_breakdown_id, start_date, end_date, name, created_at
            """,
            breakdown_id, payload.start_date, payload.end_date, payload.name,
        )
    except HTTPException:
        raise
    except Exception:
        log.error(
            "create_breakdown_range: error table=%s breakdown=%s",
            table, breakdown_id, exc_info=True,
        )
        raise
    log.info("create_breakdown_range: exit table=%s id=%s", table, row["id"])
    return DateRangeRead(**dict(row))


async def _update_range(
    conn: asyncpg.Connection,
    table: str,
    breakdown_id: UUID,
    range_id: UUID,
    payload: DateRangeUpdate,
) -> DateRangeRead:
    log.info(
        "update_breakdown_range: entry table=%s breakdown=%s id=%s",
        table, breakdown_id, range_id,
    )
    try:
        await _require_draft(conn, breakdown_id)
        current = await _validate_range_belongs(conn, table, breakdown_id, range_id)

        new_start = payload.start_date if payload.start_date is not None else current["start_date"]
        new_end = payload.end_date if payload.end_date is not None else current["end_date"]
        _reject_inverted_range(new_start, new_end)

        sets: list[str] = []
        params: list = []
        if payload.start_date is not None:
            params.append(payload.start_date)
            sets.append(f"start_date = ${len(params)}")
        if payload.end_date is not None:
            params.append(payload.end_date)
            sets.append(f"end_date = ${len(params)}")
        if payload.name is not None:
            params.append(payload.name)
            sets.append(f"name = ${len(params)}")
        if not sets:
            log.info("update_breakdown_range: no-op table=%s id=%s", table, range_id)
            return DateRangeRead(**dict(current))
        params.append(range_id)
        row = await conn.fetchrow(
            f"""
            UPDATE {table}
            SET {", ".join(sets)}
            WHERE id = ${len(params)}
            RETURNING id, syllabus_breakdown_id, start_date, end_date, name, created_at
            """,
            *params,
        )
    except HTTPException:
        raise
    except Exception:
        log.error(
            "update_breakdown_range: error table=%s breakdown=%s id=%s",
            table, breakdown_id, range_id, exc_info=True,
        )
        raise
    log.info("update_breakdown_range: exit table=%s id=%s", table, range_id)
    return DateRangeRead(**dict(row))


async def _delete_range(
    conn: asyncpg.Connection,
    table: str,
    breakdown_id: UUID,
    range_id: UUID,
) -> None:
    log.info(
        "delete_breakdown_range: entry table=%s breakdown=%s id=%s",
        table, breakdown_id, range_id,
    )
    try:
        await _require_draft(conn, breakdown_id)
        await _validate_range_belongs(conn, table, breakdown_id, range_id)
        await conn.execute(f"DELETE FROM {table} WHERE id = $1", range_id)
    except HTTPException:
        raise
    except Exception:
        log.error(
            "delete_breakdown_range: error table=%s breakdown=%s id=%s",
            table, breakdown_id, range_id, exc_info=True,
        )
        raise
    log.info("delete_breakdown_range: exit table=%s id=%s deleted", table, range_id)


@router.post(
    "/syllabus-breakdowns/{breakdown_id}/exam-periods",
    response_model=DateRangeRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_exam_period(
    breakdown_id: UUID,
    payload: DateRangeCreate,
    _org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> DateRangeRead:
    return await _create_range(conn, _RANGE_TABLES["exam-periods"], breakdown_id, payload)


@router.patch(
    "/syllabus-breakdowns/{breakdown_id}/exam-periods/{ep_id}",
    response_model=DateRangeRead,
)
async def update_exam_period(
    breakdown_id: UUID,
    ep_id: UUID,
    payload: DateRangeUpdate,
    _org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> DateRangeRead:
    return await _update_range(conn, _RANGE_TABLES["exam-periods"], breakdown_id, ep_id, payload)


@router.delete(
    "/syllabus-breakdowns/{breakdown_id}/exam-periods/{ep_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_exam_period(
    breakdown_id: UUID,
    ep_id: UUID,
    _org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> None:
    await _delete_range(conn, _RANGE_TABLES["exam-periods"], breakdown_id, ep_id)


@router.post(
    "/syllabus-breakdowns/{breakdown_id}/holidays",
    response_model=DateRangeRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_holiday(
    breakdown_id: UUID,
    payload: DateRangeCreate,
    _org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> DateRangeRead:
    return await _create_range(conn, _RANGE_TABLES["holidays"], breakdown_id, payload)


@router.patch(
    "/syllabus-breakdowns/{breakdown_id}/holidays/{h_id}",
    response_model=DateRangeRead,
)
async def update_holiday(
    breakdown_id: UUID,
    h_id: UUID,
    payload: DateRangeUpdate,
    _org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> DateRangeRead:
    return await _update_range(conn, _RANGE_TABLES["holidays"], breakdown_id, h_id, payload)


@router.delete(
    "/syllabus-breakdowns/{breakdown_id}/holidays/{h_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_holiday(
    breakdown_id: UUID,
    h_id: UUID,
    _org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> None:
    await _delete_range(conn, _RANGE_TABLES["holidays"], breakdown_id, h_id)


# ---------------------------------------------------------------------------
# Sub-SLO breakdown trigger (F2.6 — D-3)
# ---------------------------------------------------------------------------


async def _subject_key_for_slo(
    conn: asyncpg.Connection, slo_id: UUID
) -> tuple[str, str]:
    """Return (subject_code, subject_key) for an SLO. 404/422 on failure."""
    row = await conn.fetchrow(
        """
        SELECT s.code AS subject_code, slos.subject_id
        FROM slos
        JOIN subjects s ON s.id = slos.subject_id
        WHERE slos.id = $1
        """,
        slo_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SLO not found")
    subject_code = row["subject_code"]
    key = SUBJECT_CODE_TO_KEY.get(subject_code)
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"subject {subject_code!r} has no breakdown prompt configured; "
                f"known: {sorted(SUBJECT_CODE_TO_KEY)}"
            ),
        )
    return subject_code, key


@router.post(
    "/slos/{slo_id}/breakdown",
    response_model=SubSLOBreakdownResponse,
)
async def trigger_single_slo_breakdown(
    slo_id: UUID,
    force: bool = Query(default=False),
    _org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SubSLOBreakdownResponse:
    """
    Sync trigger: break down one SLO's sub-SLOs via the LLM.
    Idempotent: already-broken-down SLOs are skipped unless force=true.
    """
    _, subject_key = await _subject_key_for_slo(conn, slo_id)
    log.info("trigger_single_slo_breakdown: slo_id=%s subject=%s force=%s", slo_id, subject_key, force)
    result = await run_breakdown_for_slos(
        conn, [slo_id], subject_key=subject_key, force=force
    )
    return SubSLOBreakdownResponse(
        slo_id=slo_id,
        subject_key=subject_key,
        inserted_sub_slo_count=result["inserted_sub_slo_count"],
        skipped=slo_id in result["skipped_slo_ids"],
        raw_response_chars=len(result["markdown"]),
    )


async def _run_bulk_breakdown(
    grouped: dict[str, list[UUID]], force: bool
) -> None:
    """Background-task helper. Opens its own DB connection from the shared pool."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        for subject_key, slo_ids in grouped.items():
            try:
                await run_breakdown_for_slos(
                    conn, slo_ids, subject_key=subject_key, force=force
                )
            except Exception:
                log.exception(
                    "bulk breakdown failed for subject_key=%s slos=%s",
                    subject_key, [str(i) for i in slo_ids],
                )


@router.post(
    "/syllabus-breakdowns/sub-slos/bulk",
    response_model=SubSLOBulkAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_bulk_sub_slo_breakdown(
    payload: SubSLOBulkRequest,
    background_tasks: BackgroundTasks,
    _org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SubSLOBulkAccepted:
    """
    Bulk trigger: queue per-subject breakdown runs in the background.
    Returns 202 once enqueued; clients poll the SLO/sub-SLO read APIs
    to observe completion.
    """
    log.info("trigger_bulk_sub_slo_breakdown: count=%d force=%s", len(payload.slo_ids), payload.force)

    rows = await conn.fetch(
        """
        SELECT slos.id, s.code AS subject_code
        FROM slos
        JOIN subjects s ON s.id = slos.subject_id
        WHERE slos.id = ANY($1::uuid[])
        """,
        payload.slo_ids,
    )
    if len(rows) != len(payload.slo_ids):
        missing = set(payload.slo_ids) - {r["id"] for r in rows}
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"slo_ids not found: {sorted(str(m) for m in missing)}",
        )

    grouped: dict[str, list[UUID]] = {}
    skipped: list[UUID] = []
    for r in rows:
        key = SUBJECT_CODE_TO_KEY.get(r["subject_code"])
        if key is None:
            skipped.append(r["id"])
            continue
        grouped.setdefault(key, []).append(r["id"])

    queued = [sid for sids in grouped.values() for sid in sids]
    if grouped:
        background_tasks.add_task(_run_bulk_breakdown, grouped, payload.force)

    return SubSLOBulkAccepted(
        accepted_slo_count=len(queued),
        skipped_slo_count=len(skipped),
        grouped_by_subject={k: len(v) for k, v in grouped.items()},
        queued_slo_ids=queued,
    )
