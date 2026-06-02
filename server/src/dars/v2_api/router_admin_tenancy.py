"""
F5.5+F5.6+F5.7+F5.8 — admin tenancy CRUD.

Create / update endpoints for schools, teachers, academic years,
classes, and CSTs. Most endpoints are gated by X-Admin-Session via
get_current_admin (admin-only setup actions).

Two endpoints — POST /classes and POST /csts — accept either
X-Admin-Session or X-API-Key via get_current_org so client apps
(teacher apps, B2B integrators) can self-serve class creation.

Read endpoints (list/get) already exist in router_tenancy.py and are
gated by X-API-Key. The teacher app uses those; the dashboard uses
both.
"""
import logging
from datetime import date
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from dars.v2_api.admin_auth import AdminContext, get_current_admin
from dars.v2_api.deps import OrgContext, get_current_org, get_db_conn

log = logging.getLogger("v2_api.admin_tenancy")

router = APIRouter(prefix="/api/v1", tags=["admin-tenancy"])


# ---------------------------------------------------------------------------
# Schools
# ---------------------------------------------------------------------------


class SchoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class SchoolUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class SchoolWritten(BaseModel):
    id: UUID
    org_id: UUID
    name: str


@router.post("/schools", response_model=SchoolWritten, status_code=status.HTTP_201_CREATED)
async def create_school(
    payload: SchoolCreate,
    admin: AdminContext = Depends(get_current_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SchoolWritten:
    row = await conn.fetchrow(
        """
        INSERT INTO schools (org_id, name)
        VALUES ($1, $2)
        RETURNING id, org_id, name
        """,
        admin.org_id, payload.name,
    )
    log.info("create_school: org=%s school=%s", admin.org_id, row["id"])
    return SchoolWritten(**dict(row))


async def _ensure_school_in_org(conn: asyncpg.Connection, school_id: UUID, org_id: UUID) -> None:
    found = await conn.fetchval(
        "SELECT org_id FROM schools WHERE id = $1", school_id
    )
    if found is None or found != org_id:
        raise HTTPException(status_code=404, detail="school not found")


@router.patch("/schools/{school_id}", response_model=SchoolWritten)
async def update_school(
    school_id: UUID,
    payload: SchoolUpdate,
    admin: AdminContext = Depends(get_current_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SchoolWritten:
    await _ensure_school_in_org(conn, school_id, admin.org_id)
    row = await conn.fetchrow(
        """
        UPDATE schools SET name = $1, updated_at = now()
        WHERE id = $2
        RETURNING id, org_id, name
        """,
        payload.name, school_id,
    )
    return SchoolWritten(**dict(row))


# ---------------------------------------------------------------------------
# Teachers
# ---------------------------------------------------------------------------


class TeacherCreate(BaseModel):
    school_id: UUID
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None


class TeacherUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None


class TeacherWritten(BaseModel):
    id: UUID
    org_id: UUID
    school_id: UUID
    name: str
    email: str | None


@router.post("/teachers", response_model=TeacherWritten, status_code=status.HTTP_201_CREATED)
async def create_teacher(
    payload: TeacherCreate,
    admin: AdminContext = Depends(get_current_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> TeacherWritten:
    await _ensure_school_in_org(conn, payload.school_id, admin.org_id)
    row = await conn.fetchrow(
        """
        INSERT INTO teachers (org_id, school_id, name, email)
        VALUES ($1, $2, $3, $4)
        RETURNING id, org_id, school_id, name, email
        """,
        admin.org_id, payload.school_id, payload.name, payload.email,
    )
    log.info("create_teacher: school=%s teacher=%s", payload.school_id, row["id"])
    return TeacherWritten(**dict(row))


async def _ensure_teacher_in_org(conn: asyncpg.Connection, teacher_id: UUID, org_id: UUID) -> None:
    found = await conn.fetchval(
        "SELECT org_id FROM teachers WHERE id = $1", teacher_id
    )
    if found is None or found != org_id:
        raise HTTPException(status_code=404, detail="teacher not found")


@router.patch("/teachers/{teacher_id}", response_model=TeacherWritten)
async def update_teacher(
    teacher_id: UUID,
    payload: TeacherUpdate,
    admin: AdminContext = Depends(get_current_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> TeacherWritten:
    await _ensure_teacher_in_org(conn, teacher_id, admin.org_id)
    sets: list[str] = []
    params: list = []
    if payload.name is not None:
        params.append(payload.name)
        sets.append(f"name = ${len(params)}")
    if payload.email is not None:
        params.append(str(payload.email))
        sets.append(f"email = ${len(params)}")
    if not sets:
        row = await conn.fetchrow(
            "SELECT id, org_id, school_id, name, email FROM teachers WHERE id = $1",
            teacher_id,
        )
        return TeacherWritten(**dict(row))
    params.append(teacher_id)
    row = await conn.fetchrow(
        f"""
        UPDATE teachers SET {', '.join(sets)}, updated_at = now()
        WHERE id = ${len(params)}
        RETURNING id, org_id, school_id, name, email
        """,
        *params,
    )
    return TeacherWritten(**dict(row))


# ---------------------------------------------------------------------------
# Academic years
# ---------------------------------------------------------------------------


class AcademicYearCreate(BaseModel):
    school_id: UUID
    name: str = Field(min_length=1, max_length=100)
    # Pydantic v2 parses ISO date strings ("YYYY-MM-DD") into datetime.date,
    # which asyncpg needs for date params (otherwise it raises DataError at
    # the bind step, before Postgres ever sees the value).
    start_date: date
    end_date: date


class AcademicYearUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class AcademicYearWritten(BaseModel):
    # start_date / end_date come back as strings because the SELECT uses
    # to_char(..., 'YYYY-MM-DD'); the response shape is contractual.
    id: UUID
    org_id: UUID
    school_id: UUID
    name: str
    start_date: str
    end_date: str


@router.post("/academic-years", response_model=AcademicYearWritten, status_code=status.HTTP_201_CREATED)
async def create_academic_year(
    payload: AcademicYearCreate,
    admin: AdminContext = Depends(get_current_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> AcademicYearWritten:
    await _ensure_school_in_org(conn, payload.school_id, admin.org_id)
    row = await conn.fetchrow(
        """
        INSERT INTO academic_years (org_id, school_id, name, start_date, end_date)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, org_id, school_id, name,
                  to_char(start_date, 'YYYY-MM-DD') AS start_date,
                  to_char(end_date, 'YYYY-MM-DD') AS end_date
        """,
        admin.org_id, payload.school_id, payload.name, payload.start_date, payload.end_date,
    )
    log.info(
        "create_ay: school=%s ay=%s start=%s end=%s",
        payload.school_id, row["id"], payload.start_date, payload.end_date,
    )
    return AcademicYearWritten(**dict(row))


async def _ensure_ay_in_org(conn: asyncpg.Connection, ay_id: UUID, org_id: UUID) -> None:
    found = await conn.fetchval(
        "SELECT org_id FROM academic_years WHERE id = $1", ay_id
    )
    if found is None or found != org_id:
        raise HTTPException(status_code=404, detail="academic year not found")


@router.patch("/academic-years/{ay_id}", response_model=AcademicYearWritten)
async def update_academic_year(
    ay_id: UUID,
    payload: AcademicYearUpdate,
    admin: AdminContext = Depends(get_current_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> AcademicYearWritten:
    await _ensure_ay_in_org(conn, ay_id, admin.org_id)
    sets: list[str] = []
    params: list = []
    if payload.name is not None:
        params.append(payload.name)
        sets.append(f"name = ${len(params)}")
    if payload.start_date is not None:
        params.append(payload.start_date)
        sets.append(f"start_date = ${len(params)}")
    if payload.end_date is not None:
        params.append(payload.end_date)
        sets.append(f"end_date = ${len(params)}")
    if not sets:
        row = await conn.fetchrow(
            """SELECT id, org_id, school_id, name,
                      to_char(start_date, 'YYYY-MM-DD') AS start_date,
                      to_char(end_date, 'YYYY-MM-DD') AS end_date
               FROM academic_years WHERE id = $1""",
            ay_id,
        )
        return AcademicYearWritten(**dict(row))
    params.append(ay_id)
    row = await conn.fetchrow(
        f"""
        UPDATE academic_years SET {', '.join(sets)}, updated_at = now()
        WHERE id = ${len(params)}
        RETURNING id, org_id, school_id, name,
                  to_char(start_date, 'YYYY-MM-DD') AS start_date,
                  to_char(end_date, 'YYYY-MM-DD') AS end_date
        """,
        *params,
    )
    return AcademicYearWritten(**dict(row))


# ---------------------------------------------------------------------------
# School classes
# ---------------------------------------------------------------------------


class SchoolClassCreate(BaseModel):
    school_id: UUID
    academic_year_id: UUID
    grade_id: UUID
    section: str = Field(min_length=1, max_length=20)
    name: str | None = None  # auto-derived if absent


class SchoolClassWritten(BaseModel):
    id: UUID
    org_id: UUID
    school_id: UUID
    academic_year_id: UUID
    grade_id: UUID
    section: str
    name: str


@router.post("/classes", response_model=SchoolClassWritten, status_code=status.HTTP_201_CREATED)
async def create_school_class(
    payload: SchoolClassCreate,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SchoolClassWritten:
    """Create a school_class. Accepts X-Admin-Session or X-API-Key —
    client apps (teacher apps, B2B integrators) can self-serve."""
    await _ensure_school_in_org(conn, payload.school_id, org.id)
    await _ensure_ay_in_org(conn, payload.academic_year_id, org.id)

    # Auto-name "Grade {N} — {section}" if not given. grades.code is an int.
    name = payload.name
    if not name:
        grade_code = await conn.fetchval(
            "SELECT code FROM grades WHERE id = $1", payload.grade_id
        )
        if grade_code is None:
            raise HTTPException(status_code=422, detail="grade not found")
        name = f"Grade {grade_code} — {payload.section}"

    row = await conn.fetchrow(
        """
        INSERT INTO school_classes (org_id, school_id, academic_year_id, grade_id, section, name)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, org_id, school_id, academic_year_id, grade_id, section, name
        """,
        org.id, payload.school_id, payload.academic_year_id,
        payload.grade_id, payload.section, name,
    )
    log.info("create_school_class: org=%s school=%s class=%s", org.id, payload.school_id, row["id"])
    return SchoolClassWritten(**dict(row))


# ---------------------------------------------------------------------------
# CSTs
# ---------------------------------------------------------------------------


class CSTCreate(BaseModel):
    school_class_id: UUID
    subject_id: UUID
    teacher_id: UUID
    book_id: UUID | None = None


class CSTUpdate(BaseModel):
    teacher_id: UUID | None = None
    book_id: UUID | None = None


class CSTWritten(BaseModel):
    id: UUID
    org_id: UUID
    school_class_id: UUID
    subject_id: UUID
    teacher_id: UUID | None
    book_id: UUID | None


@router.post("/csts", response_model=CSTWritten, status_code=status.HTTP_201_CREATED)
async def create_cst(
    payload: CSTCreate,
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> CSTWritten:
    """Create a CST (class × subject × teacher). Accepts X-Admin-Session
    or X-API-Key — client apps can self-serve.

    Teachers generate their own chapter plans (Phase 2+), so CST creation
    no longer auto-forks/realizes a breakdown chain.
    """
    # tenancy + tie-ups
    klass = await conn.fetchrow(
        "SELECT org_id, school_id, grade_id FROM school_classes WHERE id = $1",
        payload.school_class_id,
    )
    if klass is None or klass["org_id"] != org.id:
        raise HTTPException(status_code=404, detail="class not found")
    await _ensure_teacher_in_org(conn, payload.teacher_id, org.id)

    row = await conn.fetchrow(
        """
        INSERT INTO class_subject_teachers (
            org_id, school_class_id, subject_id, teacher_id, book_id
        )
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, org_id, school_class_id, subject_id, teacher_id, book_id
        """,
        org.id, payload.school_class_id, payload.subject_id,
        payload.teacher_id, payload.book_id,
    )
    log.info("create_cst: org=%s class=%s cst=%s", org.id, payload.school_class_id, row["id"])

    return CSTWritten(**dict(row))


@router.patch("/csts/{cst_id}", response_model=CSTWritten)
async def update_cst(
    cst_id: UUID,
    payload: CSTUpdate,
    admin: AdminContext = Depends(get_current_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> CSTWritten:
    found = await conn.fetchval(
        "SELECT org_id FROM class_subject_teachers WHERE id = $1", cst_id
    )
    if found is None or found != admin.org_id:
        raise HTTPException(status_code=404, detail="cst not found")

    sets: list[str] = []
    params: list = []
    if payload.teacher_id is not None:
        await _ensure_teacher_in_org(conn, payload.teacher_id, admin.org_id)
        params.append(payload.teacher_id)
        sets.append(f"teacher_id = ${len(params)}")
    if payload.book_id is not None:
        params.append(payload.book_id)
        sets.append(f"book_id = ${len(params)}")
    if not sets:
        row = await conn.fetchrow(
            "SELECT id, org_id, school_class_id, subject_id, teacher_id, book_id "
            "FROM class_subject_teachers WHERE id = $1",
            cst_id,
        )
        return CSTWritten(**dict(row))
    params.append(cst_id)
    row = await conn.fetchrow(
        f"""
        UPDATE class_subject_teachers SET {', '.join(sets)}, updated_at = now()
        WHERE id = ${len(params)}
        RETURNING id, org_id, school_class_id, subject_id, teacher_id, book_id
        """,
        *params,
    )
    return CSTWritten(**dict(row))
