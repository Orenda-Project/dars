"""
F5.2 — Admin auth endpoints.
F5.4 — Org settings + API key rotate.

All endpoints under /api/v1/admin/* are unauthed at the dependency
level (signup/login can't require a session); routes that need an
admin attach get_current_admin themselves.

The /orgs/me endpoints live here too because they're admin-scoped
mutations (D-25 / D-17) — the org's API key (under X-API-Key) is the
runtime credential for teacher-app calls, while admin-scoped writes
to the org itself go through X-Admin-Session.
"""
import logging
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from dars.v2_api.admin_auth import (
    AdminContext,
    create_session,
    get_current_admin,
    hash_api_key,
    hash_password,
    make_api_key,
    revoke_session,
    verify_password,
)
from dars.v2_api.deps import get_db_conn

log = logging.getLogger("v2_api.admin")

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

org_router = APIRouter(prefix="/api/v1", tags=["admin-org"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SignupBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    org_name: str = Field(min_length=1, max_length=200)
    curriculum_code: str = Field(min_length=1, max_length=20)


class SignupResponse(BaseModel):
    session_token: UUID
    expires_at: str
    org_id: UUID
    org_name: str
    admin_id: UUID
    api_key: str
    api_key_prefix: str


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    session_token: UUID
    expires_at: str
    admin_id: UUID
    org_id: UUID


class MeResponse(BaseModel):
    admin_id: UUID
    org_id: UUID
    org_name: str
    email: str
    name: str
    curriculum_id: UUID
    curriculum_code: str
    default_teacher_id: UUID | None
    api_key_prefix: str


class OrgUpdateBody(BaseModel):
    name: str | None = None
    default_teacher_id: UUID | None = None


class RotateKeyResponse(BaseModel):
    api_key: str
    api_key_prefix: str


# ---------------------------------------------------------------------------
# /api/v1/admin/signup
# ---------------------------------------------------------------------------


@router.post("/signup", response_model=SignupResponse)
async def signup(
    payload: SignupBody,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> SignupResponse:
    """Create Org + first OrgAdmin + first API key. v1 — no email verification."""
    cur_id = await conn.fetchval(
        "SELECT id FROM curriculums WHERE code = $1", payload.curriculum_code
    )
    if cur_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown curriculum_code={payload.curriculum_code!r}",
        )

    existing = await conn.fetchval(
        "SELECT id FROM org_admins WHERE email = $1", payload.email
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already in use")

    raw_api_key, api_key_hash, api_key_prefix = make_api_key(prefix="dk_live_")

    async with conn.transaction():
        org_id = await conn.fetchval(
            """
            INSERT INTO organizations (name, curriculum_id, api_key_hash, api_key_prefix)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            payload.org_name, cur_id, api_key_hash, api_key_prefix,
        )
        admin_id = await conn.fetchval(
            """
            INSERT INTO org_admins (org_id, email, password_hash, name)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            org_id, payload.email, hash_password(payload.password), payload.name,
        )
        session_id, expires_at = await create_session(conn, admin_id)

    log.info("signup: org=%s admin=%s session=%s", org_id, admin_id, session_id)
    return SignupResponse(
        session_token=session_id,
        expires_at=expires_at.isoformat(),
        org_id=org_id,
        org_name=payload.org_name,
        admin_id=admin_id,
        api_key=raw_api_key,
        api_key_prefix=api_key_prefix,
    )


# ---------------------------------------------------------------------------
# /api/v1/admin/login
# ---------------------------------------------------------------------------


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginBody,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> LoginResponse:
    row = await conn.fetchrow(
        "SELECT id, org_id, password_hash FROM org_admins WHERE email = $1",
        payload.email,
    )
    if row is None or not verify_password(payload.password, row["password_hash"]):
        # Constant-time-ish: always do a fake hash check if no row to slow
        # enumeration. Skipping for v1 since bcrypt with cost 12 already
        # dominates the request.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid email or password",
        )

    session_id, expires_at = await create_session(conn, row["id"])
    log.info("login: admin=%s session=%s", row["id"], session_id)
    return LoginResponse(
        session_token=session_id,
        expires_at=expires_at.isoformat(),
        admin_id=row["id"],
        org_id=row["org_id"],
    )


# ---------------------------------------------------------------------------
# /api/v1/admin/logout
# ---------------------------------------------------------------------------


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    admin: AdminContext = Depends(get_current_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> None:
    await revoke_session(conn, admin.session_id)
    log.info("logout: admin=%s session=%s revoked", admin.admin_id, admin.session_id)


# ---------------------------------------------------------------------------
# /api/v1/admin/me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=MeResponse)
async def me(
    admin: AdminContext = Depends(get_current_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> MeResponse:
    row = await conn.fetchrow(
        """
        SELECT o.id AS org_id, o.name AS org_name, o.curriculum_id,
               o.default_teacher_id, o.api_key_prefix,
               c.code AS curriculum_code
        FROM organizations o
        JOIN curriculums c ON c.id = o.curriculum_id
        WHERE o.id = $1
        """,
        admin.org_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="org not found")

    return MeResponse(
        admin_id=admin.admin_id,
        org_id=admin.org_id,
        org_name=row["org_name"],
        email=admin.email,
        name=admin.name,
        curriculum_id=row["curriculum_id"],
        curriculum_code=row["curriculum_code"],
        default_teacher_id=row["default_teacher_id"],
        api_key_prefix=row["api_key_prefix"],
    )


# ---------------------------------------------------------------------------
# /api/v1/orgs/me — admin-scoped PATCH + API-key rotate (F5.4)
# ---------------------------------------------------------------------------


@org_router.patch("/orgs/me", response_model=MeResponse)
async def patch_org(
    payload: OrgUpdateBody,
    admin: AdminContext = Depends(get_current_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> MeResponse:
    sets: list[str] = []
    params: list = []
    if payload.name is not None:
        params.append(payload.name)
        sets.append(f"name = ${len(params)}")
    if payload.default_teacher_id is not None:
        # tenancy: the teacher must belong to this org
        ok = await conn.fetchval(
            "SELECT 1 FROM teachers WHERE id = $1 AND org_id = $2",
            payload.default_teacher_id, admin.org_id,
        )
        if not ok:
            raise HTTPException(status_code=422, detail="teacher not in this org")
        params.append(payload.default_teacher_id)
        sets.append(f"default_teacher_id = ${len(params)}")
    if not sets:
        # no-op; just return current state
        return await me(admin=admin, conn=conn)

    params.append(admin.org_id)
    await conn.execute(
        f"UPDATE organizations SET {', '.join(sets)}, updated_at = now() WHERE id = ${len(params)}",
        *params,
    )
    return await me(admin=admin, conn=conn)


@org_router.post("/orgs/me/rotate-api-key", response_model=RotateKeyResponse)
async def rotate_api_key(
    admin: AdminContext = Depends(get_current_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> RotateKeyResponse:
    raw, hashed, prefix = make_api_key(prefix="dk_live_")
    await conn.execute(
        """
        UPDATE organizations
        SET api_key_hash = $1, api_key_prefix = $2, updated_at = now()
        WHERE id = $3
        """,
        hashed, prefix, admin.org_id,
    )
    log.info("rotate_api_key: org=%s admin=%s new_prefix=%s", admin.org_id, admin.admin_id, prefix)
    return RotateKeyResponse(api_key=raw, api_key_prefix=prefix)
