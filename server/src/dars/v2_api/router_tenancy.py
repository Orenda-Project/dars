"""
F1.6 — Read-only API for tenancy entities.

All endpoints filter by org_id (the auth'd OrgContext) to enforce tenancy
isolation (Critical Rule #3).
"""
import logging
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from dars.v2_api.deps import OrgContext, get_current_org, get_db_conn
from dars.v2_api.schemas import (
    AcademicYearListResponse,
    AcademicYearRead,
    CSTListResponse,
    CSTRead,
    OrgRead,
    SchoolClassListResponse,
    SchoolClassRead,
    SchoolListResponse,
    SchoolRead,
    TeacherListResponse,
    TeacherRead,
)

log = logging.getLogger("v2_api.tenancy")

router = APIRouter(prefix="/api/v2", tags=["v2-tenancy"])


# ---------------------------------------------------------------------------
# Org
# ---------------------------------------------------------------------------

@router.get("/orgs/me", response_model=OrgRead)
async def get_my_org(
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> OrgRead:
    row = await conn.fetchrow(
        """
        SELECT id, name, curriculum_id, api_key_prefix, default_teacher_id, created_at, updated_at
        FROM organizations
        WHERE id = $1
        """,
        org.id,
    )
    if row is None:  # defensive; auth resolved it just now
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Org not found")
    return OrgRead(**dict(row))


# ---------------------------------------------------------------------------
# Schools
# ---------------------------------------------------------------------------

@router.get("/schools", response_model=SchoolListResponse)
async def list_schools(
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SchoolListResponse:
    rows = await conn.fetch(
        """
        SELECT id, org_id, name, created_at, updated_at
        FROM schools
        WHERE org_id = $1
        ORDER BY name
        """,
        org.id,
    )
    return SchoolListResponse(items=[SchoolRead(**dict(r)) for r in rows])


@router.get("/schools/{school_id}", response_model=SchoolRead)
async def get_school(
    school_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SchoolRead:
    row = await conn.fetchrow(
        """
        SELECT id, org_id, name, created_at, updated_at
        FROM schools
        WHERE id = $1 AND org_id = $2
        """,
        school_id, org.id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")
    return SchoolRead(**dict(row))


# ---------------------------------------------------------------------------
# Teachers
# ---------------------------------------------------------------------------

@router.get("/teachers", response_model=TeacherListResponse)
async def list_teachers(
    school_id: UUID | None = Query(default=None),
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> TeacherListResponse:
    if school_id is not None:
        rows = await conn.fetch(
            """
            SELECT id, org_id, school_id, name, email, created_at, updated_at
            FROM teachers
            WHERE org_id = $1 AND school_id = $2
            ORDER BY name
            """,
            org.id, school_id,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id, org_id, school_id, name, email, created_at, updated_at
            FROM teachers
            WHERE org_id = $1
            ORDER BY name
            """,
            org.id,
        )
    return TeacherListResponse(items=[TeacherRead(**dict(r)) for r in rows])


@router.get("/teachers/{teacher_id}", response_model=TeacherRead)
async def get_teacher(
    teacher_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> TeacherRead:
    row = await conn.fetchrow(
        """
        SELECT id, org_id, school_id, name, email, created_at, updated_at
        FROM teachers
        WHERE id = $1 AND org_id = $2
        """,
        teacher_id, org.id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    return TeacherRead(**dict(row))


# ---------------------------------------------------------------------------
# Academic Years
# ---------------------------------------------------------------------------

@router.get("/academic-years", response_model=AcademicYearListResponse)
async def list_academic_years(
    school_id: UUID | None = Query(default=None),
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> AcademicYearListResponse:
    if school_id is not None:
        rows = await conn.fetch(
            """
            SELECT id, org_id, school_id, name, start_date, end_date, created_at, updated_at
            FROM academic_years
            WHERE org_id = $1 AND school_id = $2
            ORDER BY start_date DESC
            """,
            org.id, school_id,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id, org_id, school_id, name, start_date, end_date, created_at, updated_at
            FROM academic_years
            WHERE org_id = $1
            ORDER BY start_date DESC
            """,
            org.id,
        )
    return AcademicYearListResponse(items=[AcademicYearRead(**dict(r)) for r in rows])


@router.get("/academic-years/{ay_id}", response_model=AcademicYearRead)
async def get_academic_year(
    ay_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> AcademicYearRead:
    row = await conn.fetchrow(
        """
        SELECT id, org_id, school_id, name, start_date, end_date, created_at, updated_at
        FROM academic_years
        WHERE id = $1 AND org_id = $2
        """,
        ay_id, org.id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")
    return AcademicYearRead(**dict(row))


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

@router.get("/classes", response_model=SchoolClassListResponse)
async def list_classes(
    school_id: UUID | None = Query(default=None),
    academic_year_id: UUID | None = Query(default=None),
    grade_id: UUID | None = Query(default=None),
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SchoolClassListResponse:
    where = ["org_id = $1"]
    params: list = [org.id]
    if school_id is not None:
        params.append(school_id)
        where.append(f"school_id = ${len(params)}")
    if academic_year_id is not None:
        params.append(academic_year_id)
        where.append(f"academic_year_id = ${len(params)}")
    if grade_id is not None:
        params.append(grade_id)
        where.append(f"grade_id = ${len(params)}")
    sql = f"""
        SELECT id, org_id, school_id, academic_year_id, grade_id, section, name,
               created_at, updated_at
        FROM school_classes
        WHERE {' AND '.join(where)}
        ORDER BY name
    """
    rows = await conn.fetch(sql, *params)
    return SchoolClassListResponse(items=[SchoolClassRead(**dict(r)) for r in rows])


@router.get("/classes/{class_id}", response_model=SchoolClassRead)
async def get_class(
    class_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SchoolClassRead:
    row = await conn.fetchrow(
        """
        SELECT id, org_id, school_id, academic_year_id, grade_id, section, name,
               created_at, updated_at
        FROM school_classes
        WHERE id = $1 AND org_id = $2
        """,
        class_id, org.id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    return SchoolClassRead(**dict(row))


# ---------------------------------------------------------------------------
# Class-Subject-Teachers
# ---------------------------------------------------------------------------

@router.get("/csts", response_model=CSTListResponse)
async def list_csts(
    school_class_id: UUID | None = Query(default=None),
    teacher_id: UUID | None = Query(default=None),
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> CSTListResponse:
    where = ["org_id = $1"]
    params: list = [org.id]
    if school_class_id is not None:
        params.append(school_class_id)
        where.append(f"school_class_id = ${len(params)}")
    if teacher_id is not None:
        params.append(teacher_id)
        where.append(f"teacher_id = ${len(params)}")
    sql = f"""
        SELECT id, org_id, school_class_id, subject_id, teacher_id, book_id,
               created_at, updated_at
        FROM class_subject_teachers
        WHERE {' AND '.join(where)}
        ORDER BY created_at
    """
    rows = await conn.fetch(sql, *params)
    return CSTListResponse(items=[CSTRead(**dict(r)) for r in rows])


@router.get("/csts/{cst_id}", response_model=CSTRead)
async def get_cst(
    cst_id: UUID,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> CSTRead:
    row = await conn.fetchrow(
        """
        SELECT
            cst.id, cst.org_id, cst.school_class_id, cst.subject_id,
            cst.teacher_id, cst.book_id, cst.created_at, cst.updated_at,
            s.current_sequence_position
        FROM class_subject_teachers cst
        LEFT JOIN cst_state s ON s.cst_id = cst.id
        WHERE cst.id = $1 AND cst.org_id = $2
        """,
        cst_id, org.id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CST not found")
    return CSTRead(**dict(row))
