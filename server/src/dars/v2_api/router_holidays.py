"""
F2.10 — Holiday inheritance endpoints (admin-only in v1).

D-26: effective holiday set is Org → School → CST. We expose:

  GET    /api/v2/orgs/{org_id}/holidays?academic_year_id=...
  POST   /api/v2/orgs/{org_id}/holidays
  GET    /api/v2/schools/{school_id}/holidays?academic_year_id=...
  POST   /api/v2/schools/{school_id}/holiday-overrides
  GET    /api/v2/csts/{cst_id}/holidays
  POST   /api/v2/csts/{cst_id}/holiday-overrides

The spec uses /orgs/me/* in places. To keep things simple in v1 we pass
org_id explicitly; the dashboard (Phase 5) can rewrite to /me later
when org-scoped auth is wired into these endpoints.
"""
import logging
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from dars.breakdown.holidays import (
    get_cst_overrides,
    get_effective_holidays,
    get_org_holidays,
    get_school_effective_holidays,
    get_school_overrides,
    resolve_cst_context,
)
from dars.v2_api.deps import get_db_conn, require_admin
from dars.v2_api.schemas_holidays import (
    CstOverrideCreate,
    HolidayCreated,
    HolidayListResponse,
    HolidayRead,
    OrgHolidayCreate,
    SchoolOverrideCreate,
)

log = logging.getLogger("v2_api.holidays")

router = APIRouter(
    prefix="/api/v2",
    tags=["v2-holidays"],
    dependencies=[Depends(require_admin)],
)


_VALID_OVERRIDE_ACTIONS = {"add", "remove"}


def _check_action(action: str) -> None:
    if action not in _VALID_OVERRIDE_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"action must be one of {sorted(_VALID_OVERRIDE_ACTIONS)}",
        )


# ---------------------------------------------------------------------------
# Org-level
# ---------------------------------------------------------------------------


@router.get("/orgs/{org_id}/holidays", response_model=HolidayListResponse)
async def list_org_holidays(
    org_id: UUID,
    academic_year_id: UUID = Query(),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> HolidayListResponse:
    # Validate AY belongs to the org for safety.
    ay_org = await conn.fetchval(
        "SELECT org_id FROM academic_years WHERE id = $1",
        academic_year_id,
    )
    if ay_org is None:
        raise HTTPException(status_code=404, detail="academic_year not found")
    if ay_org != org_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="academic_year does not belong to org",
        )

    rows = await conn.fetch(
        """
        SELECT date, name FROM org_holidays
        WHERE academic_year_id = $1
        ORDER BY date
        """,
        academic_year_id,
    )
    items = [HolidayRead(date=r["date"], name=r["name"], source="org") for r in rows]
    return HolidayListResponse(
        items=items,
        effective_dates=sorted({r["date"] for r in rows}),
    )


@router.post(
    "/orgs/{org_id}/holidays",
    response_model=HolidayCreated,
    status_code=status.HTTP_201_CREATED,
)
async def add_org_holiday(
    org_id: UUID,
    payload: OrgHolidayCreate,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> HolidayCreated:
    ay = await conn.fetchrow(
        "SELECT id, org_id FROM academic_years WHERE id = $1",
        payload.academic_year_id,
    )
    if ay is None:
        raise HTTPException(status_code=404, detail="academic_year not found")
    if ay["org_id"] != org_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="academic_year does not belong to org",
        )
    row = await conn.fetchrow(
        """
        INSERT INTO org_holidays (org_id, academic_year_id, date, name)
        VALUES ($1, $2, $3, $4)
        RETURNING id, date
        """,
        org_id, payload.academic_year_id, payload.date, payload.name,
    )
    log.info("add_org_holiday: org=%s ay=%s date=%s", org_id, payload.academic_year_id, payload.date)
    return HolidayCreated(**dict(row))


# ---------------------------------------------------------------------------
# School-level
# ---------------------------------------------------------------------------


@router.get("/schools/{school_id}/holidays", response_model=HolidayListResponse)
async def list_school_holidays(
    school_id: UUID,
    academic_year_id: UUID = Query(),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> HolidayListResponse:
    school = await conn.fetchrow(
        "SELECT id, org_id FROM schools WHERE id = $1", school_id
    )
    if school is None:
        raise HTTPException(status_code=404, detail="school not found")

    org_set = await get_org_holidays(conn, academic_year_id)
    overrides = await get_school_overrides(conn, school_id)
    effective = await get_school_effective_holidays(conn, school_id, academic_year_id)

    items: list[HolidayRead] = [
        HolidayRead(date=d, source="org") for d in sorted(org_set)
    ] + [
        HolidayRead(date=ov["date"], action=ov["action"], source="school")
        for ov in overrides
    ]
    return HolidayListResponse(items=items, effective_dates=sorted(effective))


@router.post(
    "/schools/{school_id}/holiday-overrides",
    response_model=HolidayCreated,
    status_code=status.HTTP_201_CREATED,
)
async def add_school_override(
    school_id: UUID,
    payload: SchoolOverrideCreate,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> HolidayCreated:
    _check_action(payload.action)
    if not await conn.fetchval("SELECT 1 FROM schools WHERE id = $1", school_id):
        raise HTTPException(status_code=404, detail="school not found")
    row = await conn.fetchrow(
        """
        INSERT INTO school_holiday_overrides (school_id, date, name, action)
        VALUES ($1, $2, $3, $4)
        RETURNING id, date
        """,
        school_id, payload.date, payload.name, payload.action,
    )
    log.info(
        "add_school_override: school=%s date=%s action=%s",
        school_id, payload.date, payload.action,
    )
    return HolidayCreated(**dict(row))


# ---------------------------------------------------------------------------
# CST-level
# ---------------------------------------------------------------------------


@router.get("/csts/{cst_id}/holidays", response_model=HolidayListResponse)
async def list_cst_holidays(
    cst_id: UUID,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> HolidayListResponse:
    try:
        _, school_id, ay_id, _ = await resolve_cst_context(conn, cst_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    org_set = await get_org_holidays(conn, ay_id)
    school_overrides = await get_school_overrides(conn, school_id)
    cst_overrides = await get_cst_overrides(conn, cst_id)
    effective = await get_effective_holidays(conn, cst_id)

    items: list[HolidayRead] = [
        HolidayRead(date=d, source="org") for d in sorted(org_set)
    ] + [
        HolidayRead(date=ov["date"], action=ov["action"], source="school")
        for ov in school_overrides
    ] + [
        HolidayRead(date=ov["date"], action=ov["action"], source="cst")
        for ov in cst_overrides
    ]
    return HolidayListResponse(items=items, effective_dates=sorted(effective))


@router.post(
    "/csts/{cst_id}/holiday-overrides",
    response_model=HolidayCreated,
    status_code=status.HTTP_201_CREATED,
)
async def add_cst_override(
    cst_id: UUID,
    payload: CstOverrideCreate,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> HolidayCreated:
    _check_action(payload.action)
    if not await conn.fetchval(
        "SELECT 1 FROM class_subject_teachers WHERE id = $1", cst_id
    ):
        raise HTTPException(status_code=404, detail="cst not found")
    row = await conn.fetchrow(
        """
        INSERT INTO cst_holiday_overrides (cst_id, date, name, action)
        VALUES ($1, $2, $3, $4)
        RETURNING id, date
        """,
        cst_id, payload.date, payload.name, payload.action,
    )
    log.info(
        "add_cst_override: cst=%s date=%s action=%s",
        cst_id, payload.date, payload.action,
    )
    return HolidayCreated(**dict(row))
