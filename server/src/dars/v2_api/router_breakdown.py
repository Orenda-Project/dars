"""
F2.4 — Breakdown CRUD endpoints (admin-only).

All endpoints in this router require X-Admin-Token (see deps.require_admin).
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
from fastapi import APIRouter, Depends, HTTPException, Query, status

from dars.breakdown.auto_build_service import (
    AutoBuildRequest,
    auto_build_breakdown,
)
from dars.v2_api.deps import get_db_conn, require_admin
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
)

log = logging.getLogger("v2_api.breakdown")

router = APIRouter(
    prefix="/api/v2",
    tags=["v2-breakdown"],
    dependencies=[Depends(require_admin)],
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


async def _require_draft(
    conn: asyncpg.Connection, breakdown_id: UUID
) -> asyncpg.Record:
    row = await _load_breakdown_or_404(conn, breakdown_id)
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
        SELECT id, breakdown_id, book_chapter_id, position, teaching_days
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

    return BreakdownRead(
        **dict(row),
        chapters=[BreakdownChapterRead(**dict(c)) for c in chapters],
        slots=[
            BreakdownSlotRead(
                **dict(s),
                extra_topics=extras_by_slot.get(s["id"], []),
            )
            for s in slots
        ],
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
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownRead:
    log.info("create_breakdown: scope=%s subject_id=%s", payload.scope, payload.subject_id)
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
    curriculum_id: UUID | None = Query(default=None),
    grade_id: UUID | None = Query(default=None),
    subject_id: UUID | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownListResponse:
    where: list[str] = ["status != 'deleted'"]
    params: list = []
    if scope is not None:
        params.append(scope)
        where.append(f"scope = ${len(params)}")
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
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownRead:
    row = await _load_breakdown_or_404(conn, breakdown_id)
    return await _hydrate_breakdown(conn, row)


@router.patch("/breakdowns/{breakdown_id}", response_model=BreakdownRead)
async def update_breakdown(
    breakdown_id: UUID,
    payload: BreakdownUpdate,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownRead:
    current = await _load_breakdown_or_404(conn, breakdown_id)
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
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownRead:
    current = await _require_draft(conn, breakdown_id)
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
    log.info("publish_breakdown: id=%s now published", breakdown_id)
    return await _hydrate_breakdown(conn, row)


@router.delete("/breakdowns/{breakdown_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_breakdown(
    breakdown_id: UUID,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> None:
    current = await _load_breakdown_or_404(conn, breakdown_id)
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
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownChapterRead:
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
            INSERT INTO breakdown_chapters (breakdown_id, book_chapter_id, position, teaching_days)
            VALUES ($1, $2, $3, $4)
            RETURNING id, breakdown_id, book_chapter_id, position, teaching_days
            """,
            breakdown_id, payload.book_chapter_id, payload.position, payload.teaching_days,
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
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownChapterRead:
    await _require_draft(conn, breakdown_id)
    await _validate_chapter_belongs_to_breakdown(conn, breakdown_id, chapter_id)
    sets: list[str] = []
    params: list = []
    if payload.position is not None:
        params.append(payload.position)
        sets.append(f"position = ${len(params)}")
    if payload.teaching_days is not None:
        params.append(payload.teaching_days)
        sets.append(f"teaching_days = ${len(params)}")
    if not sets:
        row = await conn.fetchrow(
            "SELECT id, breakdown_id, book_chapter_id, position, teaching_days FROM breakdown_chapters WHERE id = $1",
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
            RETURNING id, breakdown_id, book_chapter_id, position, teaching_days
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
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownSlotRead:
    bd = await _require_draft(conn, breakdown_id)
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
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> BreakdownSlotRead:
    bd = await _require_draft(conn, breakdown_id)
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
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> None:
    await _require_draft(conn, breakdown_id)
    await _validate_slot_belongs_to_breakdown(conn, breakdown_id, slot_id)
    await conn.execute("DELETE FROM breakdown_slots WHERE id = $1", slot_id)
    log.info("delete_slot: breakdown=%s slot=%s removed", breakdown_id, slot_id)


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
