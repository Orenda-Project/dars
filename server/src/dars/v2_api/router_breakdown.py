"""
F2.4 — Breakdown CRUD endpoints.

Auth: all endpoints take get_current_org (X-API-Key OR X-Admin-Session).
Access is scoped to the caller's org:

  - global   → readable + forkable by anyone within the same curriculum;
               creation/edit/delete remains technically open but is gated
               by org context (no anonymous access)
  - org      → scope_ref_id must equal caller's org.id
  - class    → scope_ref_id must point to a CST whose school_class belongs
               to the caller's org

Published breakdowns are immutable (PATCH/DELETE on chapters or slots → 409).
PATCH on a published breakdown itself creates a new draft version with
previous_version_id set (D-18). Publish flips status: 'draft' → 'published'.
Delete on a draft is soft (status='deleted'); delete on a published is 409.

For v2 phase 2 the publish flow only changes the row's status. F2.9 wires
realization (instantiating per-CST slots) into the same path for
class-scope breakdowns.
"""
import logging
from datetime import date
from uuid import UUID

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from dars.breakdown.auto_build_service import (
    AutoBuildRequest,
    auto_build_breakdown,
)
from dars.config import settings
from dars.breakdown.chapter_calendar import (
    compute_range_warnings,
    derived_teaching_days,
    resolve_breakdown_holidays,
)
from dars.breakdown.fork_service import fork_breakdown
from dars.breakdown.realize_service import realize_class_breakdown
from dars.breakdown.slo_breakdown_service import (
    SUBJECT_CODE_TO_KEY,
    run_breakdown_for_slos,
)
from dars.generated_lps.batch_service import (
    enqueue_for_breakdown,
    generation_status_for_breakdown,
)
from dars.v2_api.deps import (
    OrgContext,
    get_current_org,
    get_db_conn,
    get_db_pool,
)
from dars.v2_api.lp_types import VALID_SLOT_TYPES, is_valid_lp_type
from dars.v2_api.schemas_breakdown import (
    AutoBuildBody,
    AutoBuildResponse,
    BreakdownChapterCreate,
    BreakdownChapterRead,
    BreakdownChapterUpdate,
    BreakdownCreate,
    BreakdownListItem,
    BreakdownListResponse,
    BreakdownRead,
    BreakdownSlotCreate,
    BreakdownSlotRead,
    BreakdownSlotTopicRead,
    BreakdownSlotUpdate,
    BreakdownUpdate,
    AnchorUpdate,
    ForkClassBody,
    ForkOrgBody,
    ForkResponse,
    RealizeResponse,
    SubSLOBreakdownResponse,
    SubSLOBulkAccepted,
    SubSLOBulkRequest,
)

log = logging.getLogger("v2_api.breakdown")

router = APIRouter(
    prefix="/api/v2",
    tags=["v2-breakdown"],
)

VALID_SCOPES = {"global", "org", "class"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_breakdown_or_404(
    conn: asyncpg.Connection, breakdown_id: UUID
) -> asyncpg.Record:
    row = await conn.fetchrow(
        """
        SELECT id, scope, scope_ref_id, curriculum_id, grade_id, subject_id,
               book_id, parent_breakdown_id, previous_version_id, status,
               total_teaching_days, created_at, updated_at
        FROM breakdowns
        WHERE id = $1
        """,
        breakdown_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Breakdown not found")
    if row["status"] == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Breakdown not found")
    return row


async def _cst_org_id(conn: asyncpg.Connection, cst_id: UUID) -> UUID | None:
    """Resolve a CST's org_id via its school_class. None if CST not found."""
    return await conn.fetchval(
        """
        SELECT sc.org_id
        FROM class_subject_teachers cst
        JOIN school_classes sc ON sc.id = cst.school_class_id
        WHERE cst.id = $1
        """,
        cst_id,
    )


async def _assert_scope_in_org(
    conn: asyncpg.Connection,
    scope: str,
    scope_ref_id: UUID | None,
    org_id: UUID,
) -> None:
    """Reject if the (scope, scope_ref_id) tuple isn't owned by org_id.

    'global' is always allowed (it has no org binding); 'org' requires
    scope_ref_id == org_id; 'class' requires the CST's school_class to
    belong to org_id.
    """
    if scope == "global":
        return
    if scope == "org":
        if scope_ref_id != org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="scope_ref_id does not belong to caller's org",
            )
        return
    if scope == "class":
        owner = await _cst_org_id(conn, scope_ref_id)  # type: ignore[arg-type]
        if owner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="CST not found",
            )
        if owner != org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CST does not belong to caller's org",
            )
        return


async def _load_breakdown_for_org(
    conn: asyncpg.Connection, breakdown_id: UUID, org_id: UUID
) -> asyncpg.Record:
    """Load a breakdown and assert the caller's org may access it."""
    row = await _load_breakdown_or_404(conn, breakdown_id)
    await _assert_scope_in_org(conn, row["scope"], row["scope_ref_id"], org_id)
    return row


async def _require_draft(
    conn: asyncpg.Connection, breakdown_id: UUID, org_id: UUID
) -> asyncpg.Record:
    row = await _load_breakdown_for_org(conn, breakdown_id, org_id)
    if row["status"] != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Breakdown is {row['status']}; only drafts can be modified",
        )
    return row


async def _subject_code(conn: asyncpg.Connection, subject_id: UUID) -> str:
    code = await conn.fetchval("SELECT code FROM subjects WHERE id = $1", subject_id)
    if code is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"subject_id {subject_id} not found",
        )
    return code


async def _validate_chapter_belongs_to_breakdown(
    conn: asyncpg.Connection, breakdown_id: UUID, chapter_id: UUID
) -> asyncpg.Record:
    row = await conn.fetchrow(
        """
        SELECT id, breakdown_id, book_chapter_id, position, teaching_days
        FROM breakdown_chapters
        WHERE id = $1 AND breakdown_id = $2
        """,
        chapter_id, breakdown_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chapter not found on this breakdown",
        )
    return row


async def _validate_slot_belongs_to_breakdown(
    conn: asyncpg.Connection, breakdown_id: UUID, slot_id: UUID
) -> asyncpg.Record:
    row = await conn.fetchrow(
        """
        SELECT id, breakdown_id, breakdown_chapter_id, position, chapter_position,
               slot_type, lp_type, topic_id, anchor_date, created_at, updated_at
        FROM breakdown_slots
        WHERE id = $1 AND breakdown_id = $2
        """,
        slot_id, breakdown_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slot not found on this breakdown",
        )
    return row


def _validate_slot_inputs(
    slot_type: str, lp_type: str | None, subject_code: str
) -> None:
    if slot_type not in VALID_SLOT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"slot_type must be one of {sorted(VALID_SLOT_TYPES)}",
        )
    if not is_valid_lp_type(subject_code, lp_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"lp_type={lp_type!r} is not valid for subject {subject_code!r}; "
                "see lp_types.LP_TYPES_BY_SUBJECT"
            ),
        )


async def _hydrate_breakdown(
    conn: asyncpg.Connection, row: asyncpg.Record
) -> BreakdownRead:
    chapters = await conn.fetch(
        """
        SELECT id, breakdown_id, book_chapter_id, position, teaching_days,
               start_date, end_date
        FROM breakdown_chapters
        WHERE breakdown_id = $1
        ORDER BY position
        """,
        row["id"],
    )
    slots = await conn.fetch(
        """
        SELECT id, breakdown_id, breakdown_chapter_id, position, chapter_position,
               slot_type, lp_type, topic_id, anchor_date, created_at, updated_at
        FROM breakdown_slots
        WHERE breakdown_id = $1
        ORDER BY position
        """,
        row["id"],
    )
    slot_ids = [s["id"] for s in slots]
    extras_by_slot: dict[UUID, list[BreakdownSlotTopicRead]] = {}
    if slot_ids:
        extra_rows = await conn.fetch(
            """
            SELECT breakdown_slot_id, topic_id, position
            FROM breakdown_slot_topics
            WHERE breakdown_slot_id = ANY($1::uuid[])
            ORDER BY breakdown_slot_id, position
            """,
            slot_ids,
        )
        for er in extra_rows:
            extras_by_slot.setdefault(er["breakdown_slot_id"], []).append(
                BreakdownSlotTopicRead(topic_id=er["topic_id"], position=er["position"])
            )

    # D-2 / D-5: derive teaching days per chapter and advisory range warnings
    # against the breakdown's best-effort academic calendar.
    holidays = await resolve_breakdown_holidays(conn, row["id"])
    chapter_dicts = [dict(c) for c in chapters]
    for c in chapter_dicts:
        c["derived_teaching_days"] = derived_teaching_days(
            c["start_date"], c["end_date"], holidays
        )
    warnings = compute_range_warnings(chapter_dicts, holidays)

    return BreakdownRead(
        **dict(row),
        chapters=[BreakdownChapterRead(**c) for c in chapter_dicts],
        slots=[
            BreakdownSlotRead(
                **dict(s),
                extra_topics=extras_by_slot.get(s["id"], []),
            )
            for s in slots
        ],
        chapter_range_warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Breakdown CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/breakdowns",
    response_model=BreakdownRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_breakdown(
    payload: BreakdownCreate,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownRead:
    log.info("create_breakdown: org=%s scope=%s subject_id=%s", org.id, payload.scope, payload.subject_id)
    if payload.scope not in VALID_SCOPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"scope must be one of {sorted(VALID_SCOPES)}",
        )
    # D-69: book_id is required for all scopes in v1 (application-layer NOT NULL).
    if payload.book_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="book_id is required (D-69)",
        )
    if payload.scope == "global" and payload.scope_ref_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scope='global' must not have scope_ref_id",
        )
    if payload.scope != "global" and payload.scope_ref_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"scope='{payload.scope}' requires scope_ref_id",
        )
    await _assert_scope_in_org(conn, payload.scope, payload.scope_ref_id, org.id)

    row = await conn.fetchrow(
        """
        INSERT INTO breakdowns (scope, scope_ref_id, curriculum_id, grade_id, subject_id,
                                book_id, total_teaching_days, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'draft')
        RETURNING id, scope, scope_ref_id, curriculum_id, grade_id, subject_id,
                  book_id, parent_breakdown_id, previous_version_id, status,
                  total_teaching_days, created_at, updated_at
        """,
        payload.scope, payload.scope_ref_id, payload.curriculum_id,
        payload.grade_id, payload.subject_id, payload.book_id,
        payload.total_teaching_days,
    )
    log.info("create_breakdown: created id=%s", row["id"])
    return await _hydrate_breakdown(conn, row)


@router.get("/breakdowns", response_model=BreakdownListResponse)
async def list_breakdowns(
    scope: str | None = Query(default=None),
    scope_ref_id: UUID | None = Query(default=None),
    curriculum_id: UUID | None = Query(default=None),
    grade_id: UUID | None = Query(default=None),
    subject_id: UUID | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownListResponse:
    # Visibility rule: global breakdowns matching the caller's curriculum,
    # plus the caller's own org-scope and class-scope rows.
    params: list = [org.id, org.curriculum_id]
    org_filter = (
        "(scope = 'global' AND curriculum_id = $2) "
        "OR (scope = 'org' AND scope_ref_id = $1) "
        "OR (scope = 'class' AND scope_ref_id IN ("
        "    SELECT cst.id FROM class_subject_teachers cst "
        "    JOIN school_classes sc ON sc.id = cst.school_class_id "
        "    WHERE sc.org_id = $1"
        "))"
    )
    where: list[str] = ["status != 'deleted'", f"({org_filter})"]
    if scope is not None:
        params.append(scope)
        where.append(f"scope = ${len(params)}")
    if scope_ref_id is not None:
        params.append(scope_ref_id)
        where.append(f"scope_ref_id = ${len(params)}")
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
        SELECT id, scope, scope_ref_id, curriculum_id, grade_id, subject_id,
               book_id, status, total_teaching_days, created_at, updated_at
        FROM breakdowns
        {where_sql}
        ORDER BY created_at DESC
        """,
        *params,
    )
    return BreakdownListResponse(items=[BreakdownListItem(**dict(r)) for r in rows])


@router.get("/breakdowns/{breakdown_id}", response_model=BreakdownRead)
async def get_breakdown(
    breakdown_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownRead:
    row = await _load_breakdown_for_org(conn, breakdown_id, org.id)
    return await _hydrate_breakdown(conn, row)


@router.patch("/breakdowns/{breakdown_id}", response_model=BreakdownRead)
async def update_breakdown(
    breakdown_id: UUID,
    payload: BreakdownUpdate,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownRead:
    current = await _load_breakdown_for_org(conn, breakdown_id, org.id)
    if current["status"] == "published":
        # D-18: PATCH on a published breakdown creates a new draft version.
        log.info("update_breakdown: published id=%s — creating new version", breakdown_id)
        new_book_id = payload.book_id if payload.book_id is not None else current["book_id"]
        new_total = (
            payload.total_teaching_days
            if payload.total_teaching_days is not None
            else current["total_teaching_days"]
        )
        row = await conn.fetchrow(
            """
            INSERT INTO breakdowns (scope, scope_ref_id, curriculum_id, grade_id, subject_id,
                                    book_id, parent_breakdown_id, previous_version_id,
                                    total_teaching_days, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'draft')
            RETURNING id, scope, scope_ref_id, curriculum_id, grade_id, subject_id,
                      book_id, parent_breakdown_id, previous_version_id, status,
                      total_teaching_days, created_at, updated_at
            """,
            current["scope"], current["scope_ref_id"], current["curriculum_id"],
            current["grade_id"], current["subject_id"], new_book_id,
            current["parent_breakdown_id"], current["id"], new_total,
        )
        return await _hydrate_breakdown(conn, row)

    if current["status"] != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Breakdown status={current['status']!r} cannot be modified",
        )

    sets: list[str] = []
    params: list = []
    if payload.total_teaching_days is not None:
        params.append(payload.total_teaching_days)
        sets.append(f"total_teaching_days = ${len(params)}")
    if payload.book_id is not None:
        params.append(payload.book_id)
        sets.append(f"book_id = ${len(params)}")
    if not sets:
        return await _hydrate_breakdown(conn, current)
    params.append(breakdown_id)
    row = await conn.fetchrow(
        f"""
        UPDATE breakdowns
        SET {", ".join(sets)}, updated_at = now()
        WHERE id = ${len(params)}
        RETURNING id, scope, scope_ref_id, curriculum_id, grade_id, subject_id,
                  book_id, parent_breakdown_id, previous_version_id, status,
                  total_teaching_days, created_at, updated_at
        """,
        *params,
    )
    return await _hydrate_breakdown(conn, row)


@router.post("/breakdowns/{breakdown_id}/publish", response_model=BreakdownRead)
async def publish_breakdown(
    breakdown_id: UUID,
    background_tasks: BackgroundTasks,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownRead:
    current = await _require_draft(conn, breakdown_id, org.id)
    row = await conn.fetchrow(
        """
        UPDATE breakdowns
        SET status = 'published', updated_at = now()
        WHERE id = $1
        RETURNING id, scope, scope_ref_id, curriculum_id, grade_id, subject_id,
                  book_id, parent_breakdown_id, previous_version_id, status,
                  total_teaching_days, created_at, updated_at
        """,
        current["id"],
    )
    # F2.9: publishing a class-scope breakdown triggers realization into
    # class_lesson_slots + class_assessment_slots for the CST.
    if row["scope"] == "class":
        try:
            await realize_class_breakdown(conn, row["id"])
        except ValueError as e:
            log.warning("publish_breakdown: realize failed id=%s: %s", row["id"], e)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"publish succeeded but realize failed: {e}",
            )
    log.info("publish_breakdown: id=%s now published", breakdown_id)

    # F3.11 — fire batch generation as a background task so publish stays fast.
    # Gated on settings.publish_auto_enqueue (default False): under the D-74
    # slot-per-day model, publishing a class-scope breakdown would fan out
    # one upstream job per teaching day (~180). Set DARS_PUBLISH_AUTO_ENQUEUE=1
    # to re-enable.
    if settings.publish_auto_enqueue:
        background_tasks.add_task(_bg_enqueue_breakdown, row["id"])
    else:
        log.info(
            "publish_breakdown: id=%s — auto-enqueue disabled (settings.publish_auto_enqueue=False)",
            breakdown_id,
        )

    return await _hydrate_breakdown(conn, row)


async def _bg_enqueue_breakdown(breakdown_id: UUID) -> None:
    """Background task wrapper: opens its own connection from the pool."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            await enqueue_for_breakdown(conn, breakdown_id)
        except Exception:  # noqa: BLE001
            log.exception("bg_enqueue_breakdown failed for id=%s", breakdown_id)


@router.get("/breakdowns/{breakdown_id}/generation-status")
async def get_generation_status(
    breakdown_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> dict:
    """F3.11 — counts of generated_lps + generated_exams by status.

    Returns:
        {
          "lp":   {"total": N, "pending": p, "in_flight": i, "ready": r, "error": e},
          "exam": {...},
        }
    """
    await _load_breakdown_for_org(conn, breakdown_id, org.id)
    try:
        return await generation_status_for_breakdown(conn, breakdown_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/breakdowns/{breakdown_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_breakdown(
    breakdown_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> None:
    current = await _load_breakdown_for_org(conn, breakdown_id, org.id)
    if current["status"] == "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a published breakdown",
        )
    await conn.execute(
        "UPDATE breakdowns SET status = 'deleted', updated_at = now() WHERE id = $1",
        breakdown_id,
    )
    log.info("delete_breakdown: soft-deleted id=%s", breakdown_id)


# ---------------------------------------------------------------------------
# Chapters
# ---------------------------------------------------------------------------


@router.post(
    "/breakdowns/{breakdown_id}/chapters",
    response_model=BreakdownChapterRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_chapter(
    breakdown_id: UUID,
    payload: BreakdownChapterCreate,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownChapterRead:
    await _require_draft(conn, breakdown_id, org.id)
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
            INSERT INTO breakdown_chapters
                (breakdown_id, book_chapter_id, position, teaching_days, start_date, end_date)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, breakdown_id, book_chapter_id, position, teaching_days,
                      start_date, end_date
            """,
            breakdown_id, payload.book_chapter_id, payload.position, payload.teaching_days,
            payload.start_date, payload.end_date,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"position {payload.position} is already taken on this breakdown",
        )
    return BreakdownChapterRead(**dict(row))


@router.patch(
    "/breakdowns/{breakdown_id}/chapters/{chapter_id}",
    response_model=BreakdownChapterRead,
)
async def update_chapter(
    breakdown_id: UUID,
    chapter_id: UUID,
    payload: BreakdownChapterUpdate,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownChapterRead:
    await _require_draft(conn, breakdown_id, org.id)
    await _validate_chapter_belongs_to_breakdown(conn, breakdown_id, chapter_id)
    sets: list[str] = []
    params: list = []
    if payload.position is not None:
        params.append(payload.position)
        sets.append(f"position = ${len(params)}")
    if payload.teaching_days is not None:
        params.append(payload.teaching_days)
        sets.append(f"teaching_days = ${len(params)}")
    # D-8: None means "omit" (consistent with the other PATCH fields); clearing
    # a date range is not supported via this endpoint in the prototype.
    if payload.start_date is not None:
        params.append(payload.start_date)
        sets.append(f"start_date = ${len(params)}")
    if payload.end_date is not None:
        params.append(payload.end_date)
        sets.append(f"end_date = ${len(params)}")
    if not sets:
        row = await conn.fetchrow(
            "SELECT id, breakdown_id, book_chapter_id, position, teaching_days, "
            "start_date, end_date FROM breakdown_chapters WHERE id = $1",
            chapter_id,
        )
        return BreakdownChapterRead(**dict(row))
    params.append(chapter_id)
    try:
        row = await conn.fetchrow(
            f"""
            UPDATE breakdown_chapters
            SET {", ".join(sets)}
            WHERE id = ${len(params)}
            RETURNING id, breakdown_id, book_chapter_id, position, teaching_days,
                      start_date, end_date
            """,
            *params,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="position conflict on this breakdown",
        )
    return BreakdownChapterRead(**dict(row))


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------


@router.post(
    "/breakdowns/{breakdown_id}/slots",
    response_model=BreakdownSlotRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_slot(
    breakdown_id: UUID,
    payload: BreakdownSlotCreate,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownSlotRead:
    bd = await _require_draft(conn, breakdown_id, org.id)
    chapter = await _validate_chapter_belongs_to_breakdown(
        conn, breakdown_id, payload.breakdown_chapter_id
    )
    subject_code = await _subject_code(conn, bd["subject_id"])
    _validate_slot_inputs(payload.slot_type, payload.lp_type, subject_code)

    # If topic_id is set, it must belong to a book_chapter referenced by the breakdown.
    if payload.topic_id is not None:
        topic_chapter = await conn.fetchval(
            "SELECT book_chapter_id FROM topics WHERE id = $1", payload.topic_id
        )
        if topic_chapter is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"topic_id {payload.topic_id} not found",
            )
        chapter_ok = await conn.fetchval(
            """
            SELECT 1 FROM breakdown_chapters
            WHERE breakdown_id = $1 AND book_chapter_id = $2
            """,
            breakdown_id, topic_chapter,
        )
        if not chapter_ok:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="topic_id belongs to a chapter not present in this breakdown",
            )

    try:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO breakdown_slots
                  (breakdown_id, breakdown_chapter_id, position, chapter_position,
                   slot_type, lp_type, topic_id, anchor_date)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id, breakdown_id, breakdown_chapter_id, position, chapter_position,
                          slot_type, lp_type, topic_id, anchor_date, created_at, updated_at
                """,
                breakdown_id, chapter["id"], payload.position, payload.chapter_position,
                payload.slot_type, payload.lp_type, payload.topic_id, payload.anchor_date,
            )
            extras: list[BreakdownSlotTopicRead] = []
            for i, t_id in enumerate(payload.extra_topic_ids, start=1):
                await conn.execute(
                    """
                    INSERT INTO breakdown_slot_topics (breakdown_slot_id, topic_id, position)
                    VALUES ($1, $2, $3)
                    """,
                    row["id"], t_id, i,
                )
                extras.append(BreakdownSlotTopicRead(topic_id=t_id, position=i))
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"position {payload.position} is already taken on this breakdown",
        )
    return BreakdownSlotRead(**dict(row), extra_topics=extras)


@router.patch(
    "/breakdowns/{breakdown_id}/slots/{slot_id}",
    response_model=BreakdownSlotRead,
)
async def update_slot(
    breakdown_id: UUID,
    slot_id: UUID,
    payload: BreakdownSlotUpdate,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownSlotRead:
    bd = await _require_draft(conn, breakdown_id, org.id)
    slot = await _validate_slot_belongs_to_breakdown(conn, breakdown_id, slot_id)
    subject_code = await _subject_code(conn, bd["subject_id"])
    effective_slot_type = payload.slot_type if payload.slot_type is not None else slot["slot_type"]
    effective_lp_type = payload.lp_type if payload.lp_type is not None else slot["lp_type"]
    # Treat any update that touches type/lp_type as a re-validation point.
    if payload.slot_type is not None or payload.lp_type is not None:
        _validate_slot_inputs(effective_slot_type, effective_lp_type, subject_code)

    sets: list[str] = []
    params: list = []
    for field in ("position", "chapter_position", "slot_type", "lp_type", "topic_id", "anchor_date"):
        value = getattr(payload, field)
        if value is not None:
            params.append(value)
            sets.append(f"{field} = ${len(params)}")
    if not sets:
        return BreakdownSlotRead(**dict(slot), extra_topics=[])
    params.append(slot_id)
    try:
        row = await conn.fetchrow(
            f"""
            UPDATE breakdown_slots
            SET {", ".join(sets)}, updated_at = now()
            WHERE id = ${len(params)}
            RETURNING id, breakdown_id, breakdown_chapter_id, position, chapter_position,
                      slot_type, lp_type, topic_id, anchor_date, created_at, updated_at
            """,
            *params,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="position conflict on this breakdown",
        )
    extras = await conn.fetch(
        "SELECT topic_id, position FROM breakdown_slot_topics WHERE breakdown_slot_id = $1 ORDER BY position",
        slot_id,
    )
    return BreakdownSlotRead(
        **dict(row),
        extra_topics=[BreakdownSlotTopicRead(**dict(e)) for e in extras],
    )


@router.delete(
    "/breakdowns/{breakdown_id}/slots/{slot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_slot(
    breakdown_id: UUID,
    slot_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> None:
    await _require_draft(conn, breakdown_id, org.id)
    await _validate_slot_belongs_to_breakdown(conn, breakdown_id, slot_id)
    await conn.execute("DELETE FROM breakdown_slots WHERE id = $1", slot_id)
    log.info("delete_slot: breakdown=%s slot=%s removed", breakdown_id, slot_id)


# ---------------------------------------------------------------------------
# Anchor placement (F2.11)
# ---------------------------------------------------------------------------


@router.patch(
    "/breakdowns/{breakdown_id}/slots/{slot_id}/anchor",
    response_model=BreakdownSlotRead,
)
async def set_slot_anchor(
    breakdown_id: UUID,
    slot_id: UUID,
    payload: AnchorUpdate,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownSlotRead:
    """
    Set or clear a slot's `anchor_date`.

    Per D-7, only admin scopes (global, org) can place anchors. Class
    scope is teachers' surface — we forbid anchor placement there to
    keep authoritative scheduling at org level. Published breakdowns
    are immutable (409) consistent with the rest of slot mutation.
    """
    bd = await _load_breakdown_for_org(conn, breakdown_id, org.id)
    if bd["scope"] not in ("global", "org"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="anchors can only be set on global or org-scope breakdowns",
        )
    if bd["status"] != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"breakdown is {bd['status']}; only drafts can be modified",
        )
    await _validate_slot_belongs_to_breakdown(conn, breakdown_id, slot_id)

    row = await conn.fetchrow(
        """
        UPDATE breakdown_slots
        SET anchor_date = $1, updated_at = now()
        WHERE id = $2
        RETURNING id, breakdown_id, breakdown_chapter_id, position, chapter_position,
                  slot_type, lp_type, topic_id, anchor_date, created_at, updated_at
        """,
        payload.anchor_date, slot_id,
    )
    extras = await conn.fetch(
        "SELECT topic_id, position FROM breakdown_slot_topics WHERE breakdown_slot_id = $1 ORDER BY position",
        slot_id,
    )
    log.info(
        "set_slot_anchor: breakdown=%s slot=%s anchor=%s",
        breakdown_id, slot_id, payload.anchor_date,
    )
    return BreakdownSlotRead(
        **dict(row),
        extra_topics=[BreakdownSlotTopicRead(**dict(e)) for e in extras],
    )


# ---------------------------------------------------------------------------
# Auto-build (F2.5)
# ---------------------------------------------------------------------------


@router.post(
    "/breakdowns/auto-build",
    response_model=AutoBuildResponse,
    status_code=status.HTTP_201_CREATED,
)
async def auto_build(
    payload: AutoBuildBody,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> AutoBuildResponse:
    """
    Build a draft breakdown from a book + curriculum using D-68 heuristics.
    Returns the new breakdown id + summary counts.
    """
    if payload.scope not in VALID_SCOPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"scope must be one of {sorted(VALID_SCOPES)}",
        )
    if payload.scope == "global" and payload.scope_ref_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scope='global' must not have scope_ref_id",
        )
    if payload.scope != "global" and payload.scope_ref_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"scope='{payload.scope}' requires scope_ref_id",
        )
    await _assert_scope_in_org(conn, payload.scope, payload.scope_ref_id, org.id)

    try:
        result = await auto_build_breakdown(
            conn,
            AutoBuildRequest(
                curriculum_id=payload.curriculum_id,
                grade_id=payload.grade_id,
                subject_id=payload.subject_id,
                book_id=payload.book_id,
                total_teaching_days=payload.total_teaching_days,
                fa_cadence=payload.fa_cadence,
                sa_per_chapter=payload.sa_per_chapter,
                scope=payload.scope,
                scope_ref_id=payload.scope_ref_id,
            ),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    return AutoBuildResponse(
        breakdown_id=result.breakdown_id,
        chapter_count=result.chapter_count,
        lesson_slot_count=result.lesson_slot_count,
        fa_slot_count=result.fa_slot_count,
        sa_slot_count=result.sa_slot_count,
        revision_slot_count=result.revision_slot_count,
        total_slot_count=result.total_slot_count,
        warnings=result.warnings,
    )


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
    "/breakdowns/sub-slos/bulk",
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
    to observe completion. Per D-42 (FastAPI BackgroundTasks for short
    schema-port jobs).
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


# ---------------------------------------------------------------------------
# Fork endpoints (F2.7)
# ---------------------------------------------------------------------------


@router.post(
    "/breakdowns/{breakdown_id}/fork-org",
    response_model=ForkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def fork_org(
    breakdown_id: UUID,
    payload: ForkOrgBody,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> ForkResponse:
    """Org admin forks a published global breakdown → org-scope draft."""
    await _load_breakdown_for_org(conn, breakdown_id, org.id)
    if payload.org_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="org_id must match caller's org",
        )
    try:
        new_id, chapters, slots = await fork_breakdown(
            conn,
            source_id=breakdown_id,
            new_scope="org",
            scope_ref_id=payload.org_id,
        )
    except ValueError as e:
        msg = str(e)
        # "already exists" → 409; everything else → 422/404
        if "already exists" in msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)
        if "not found" in msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
    return ForkResponse(
        new_breakdown_id=new_id,
        parent_breakdown_id=breakdown_id,
        new_scope="org",
        scope_ref_id=payload.org_id,
        copied_chapter_count=chapters,
        copied_slot_count=slots,
    )


@router.post(
    "/breakdowns/{breakdown_id}/fork-class",
    response_model=ForkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def fork_class(
    breakdown_id: UUID,
    payload: ForkClassBody,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> ForkResponse:
    """Org admin forks a published org breakdown → class-scope draft for a CST."""
    await _load_breakdown_for_org(conn, breakdown_id, org.id)
    cst_owner = await _cst_org_id(conn, payload.cst_id)
    if cst_owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CST not found")
    if cst_owner != org.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CST does not belong to caller's org",
        )
    try:
        new_id, chapters, slots = await fork_breakdown(
            conn,
            source_id=breakdown_id,
            new_scope="class",
            scope_ref_id=payload.cst_id,
        )
    except ValueError as e:
        msg = str(e)
        if "already exists" in msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)
        if "not found" in msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
    return ForkResponse(
        new_breakdown_id=new_id,
        parent_breakdown_id=breakdown_id,
        new_scope="class",
        scope_ref_id=payload.cst_id,
        copied_chapter_count=chapters,
        copied_slot_count=slots,
    )


# ---------------------------------------------------------------------------
# Realize (F2.9) — manual re-trigger; publish-class auto-runs this too.
# ---------------------------------------------------------------------------


@router.post(
    "/breakdowns/{breakdown_id}/realize",
    response_model=RealizeResponse,
)
async def realize(
    breakdown_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> RealizeResponse:
    await _load_breakdown_for_org(conn, breakdown_id, org.id)
    try:
        res = await realize_class_breakdown(conn, breakdown_id)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
    return RealizeResponse(
        breakdown_id=res.breakdown_id,
        cst_id=res.cst_id,
        lesson_slots_upserted=res.lesson_slots_upserted,
        assessment_slots_upserted=res.assessment_slots_upserted,
        assessment_topics_inserted=res.assessment_topics_inserted,
        skipped=res.skipped,
    )
