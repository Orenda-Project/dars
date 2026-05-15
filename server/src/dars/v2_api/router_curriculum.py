"""
F1.7 — Read-only API for curriculum entities.

Public endpoints (no API key required) since curriculum data is global
per D-24. Auth-protected SLO endpoints would force every demo of the
breakdown engine to pass an API key for what is fundamentally reference
data; opting out keeps the surface clean.
"""
import logging
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from dars.v2_api.deps import get_db_conn
from dars.v2_api.schemas_curriculum import (
    CurriculumListResponse,
    CurriculumRead,
    GradeListResponse,
    GradeRead,
    SLOListResponse,
    SLORead,
    SubjectListResponse,
    SubjectRead,
    SubSLOListResponse,
    SubSLORead,
)

log = logging.getLogger("v2_api.curriculum")

router = APIRouter(prefix="/api/v2", tags=["v2-curriculum"])


# ---------------------------------------------------------------------------
# Lookups (public)
# ---------------------------------------------------------------------------

@router.get("/curriculums", response_model=CurriculumListResponse)
async def list_curriculums(
    is_active: bool | None = Query(default=None),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> CurriculumListResponse:
    if is_active is not None:
        rows = await conn.fetch(
            "SELECT id, code, name, description, is_active FROM curriculums WHERE is_active = $1 ORDER BY code",
            is_active,
        )
    else:
        rows = await conn.fetch(
            "SELECT id, code, name, description, is_active FROM curriculums ORDER BY code"
        )
    return CurriculumListResponse(items=[CurriculumRead(**dict(r)) for r in rows])


@router.get("/curriculums/{curriculum_id}", response_model=CurriculumRead)
async def get_curriculum(
    curriculum_id: UUID,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> CurriculumRead:
    row = await conn.fetchrow(
        "SELECT id, code, name, description, is_active FROM curriculums WHERE id = $1",
        curriculum_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curriculum not found")
    return CurriculumRead(**dict(row))


@router.get("/grades", response_model=GradeListResponse)
async def list_grades(
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> GradeListResponse:
    rows = await conn.fetch("SELECT id, code, display_name FROM grades ORDER BY code")
    return GradeListResponse(items=[GradeRead(**dict(r)) for r in rows])


@router.get("/subjects", response_model=SubjectListResponse)
async def list_subjects(
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SubjectListResponse:
    rows = await conn.fetch("SELECT id, code, display_name FROM subjects ORDER BY code")
    return SubjectListResponse(items=[SubjectRead(**dict(r)) for r in rows])


# ---------------------------------------------------------------------------
# SLOs and Sub-SLOs (public)
# ---------------------------------------------------------------------------

@router.get("/slos", response_model=SLOListResponse)
async def list_slos(
    curriculum_id: UUID | None = Query(default=None),
    grade_id: UUID | None = Query(default=None),
    subject_id: UUID | None = Query(default=None),
    include_sub_slos: bool = Query(default=False, description="Embed sub-SLOs per SLO"),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SLOListResponse:
    where = []
    params: list = []
    if curriculum_id is not None:
        params.append(curriculum_id)
        where.append(f"curriculum_id = ${len(params)}")
    if grade_id is not None:
        params.append(grade_id)
        where.append(f"grade_id = ${len(params)}")
    if subject_id is not None:
        params.append(subject_id)
        where.append(f"subject_id = ${len(params)}")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = await conn.fetch(
        f"""
        SELECT id, curriculum_id, grade_id, subject_id, code, statement, domain, position,
               recommended_lp_type, created_at, updated_at
        FROM slos
        {where_sql}
        ORDER BY position, code
        """,
        *params,
    )
    items = [SLORead(**dict(r)) for r in rows]

    if include_sub_slos and items:
        slo_ids = [s.id for s in items]
        sub_rows = await conn.fetch(
            """
            SELECT id, slo_id, code, statement, position, source
            FROM sub_slos
            WHERE slo_id = ANY($1::uuid[])
            ORDER BY slo_id, position, code
            """,
            slo_ids,
        )
        by_parent: dict[UUID, list[SubSLORead]] = {}
        for r in sub_rows:
            by_parent.setdefault(r["slo_id"], []).append(SubSLORead(**dict(r)))
        for item in items:
            item.sub_slos = by_parent.get(item.id, [])

    return SLOListResponse(items=items)


@router.get("/slos/{slo_id}", response_model=SLORead)
async def get_slo(
    slo_id: UUID,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SLORead:
    row = await conn.fetchrow(
        """
        SELECT id, curriculum_id, grade_id, subject_id, code, statement, domain, position,
               recommended_lp_type, created_at, updated_at
        FROM slos WHERE id = $1
        """,
        slo_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SLO not found")
    item = SLORead(**dict(row))
    sub_rows = await conn.fetch(
        """
        SELECT id, slo_id, code, statement, position, source
        FROM sub_slos WHERE slo_id = $1 ORDER BY position, code
        """,
        slo_id,
    )
    item.sub_slos = [SubSLORead(**dict(r)) for r in sub_rows]
    return item


@router.get("/sub-slos", response_model=SubSLOListResponse)
async def list_sub_slos(
    slo_id: UUID | None = Query(default=None),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SubSLOListResponse:
    if slo_id is not None:
        rows = await conn.fetch(
            """
            SELECT id, slo_id, code, statement, position, source
            FROM sub_slos WHERE slo_id = $1 ORDER BY position, code
            """,
            slo_id,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id, slo_id, code, statement, position, source
            FROM sub_slos ORDER BY slo_id, position, code
            """
        )
    return SubSLOListResponse(items=[SubSLORead(**dict(r)) for r in rows])


@router.get("/sub-slos/{sub_slo_id}", response_model=SubSLORead)
async def get_sub_slo(
    sub_slo_id: UUID,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SubSLORead:
    row = await conn.fetchrow(
        """
        SELECT id, slo_id, code, statement, position, source
        FROM sub_slos WHERE id = $1
        """,
        sub_slo_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-SLO not found")
    return SubSLORead(**dict(row))
