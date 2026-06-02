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
from uuid import UUID

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from dars.breakdown.chapter_calendar import (
    compute_range_warnings,
    derived_teaching_days,
    resolve_breakdown_holidays,
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

    # D-2 / D-5: derive teaching days per chapter and advisory range warnings.
    # Global syllabus breakdowns have no academic calendar -> no holidays.
    holidays = await resolve_breakdown_holidays(conn, row["id"])
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
