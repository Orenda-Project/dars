"""
F2.10 — Holiday inheritance endpoints.

Auth: get_current_org (X-API-Key OR X-Admin-Session). Cross-org access
is rejected: org_id path param must equal caller's org; school_id and
cst_id are validated to belong to caller's org.

D-26: effective holiday set is Org → School → CST. We expose:

  GET    /api/v2/orgs/{org_id}/holidays?academic_year_id=...
  POST   /api/v2/orgs/{org_id}/holidays
  GET    /api/v2/schools/{school_id}/holidays?academic_year_id=...
  POST   /api/v2/schools/{school_id}/holiday-overrides
  GET    /api/v2/csts/{cst_id}/holidays
  POST   /api/v2/csts/{cst_id}/holiday-overrides
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
from dars.v2_api.deps import OrgContext, get_current_org, get_db_conn
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
)


_VALID_OVERRIDE_ACTIONS = {"add", "remove"}


def _assert_org_match(path_org_id: UUID, caller_org_id: UUID) -> None:
    if path_org_id != caller_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="org_id does not match caller's org",
        )


async def _assert_school_in_org(
    conn: asyncpg.Connection, school_id: UUID, caller_org_id: UUID
) -> None:
    owner = await conn.fetchval("SELECT org_id FROM schools WHERE id = $1", school_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="school not found")
    if owner != caller_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="school does not belong to caller's org",
        )


async def _assert_cst_in_org(
    conn: asyncpg.Connection, cst_id: UUID, caller_org_id: UUID
) -> None:
    owner = await conn.fetchval(
        """
        SELECT sc.org_id
        FROM class_subject_teachers cst
        JOIN school_classes sc ON sc.id = cst.school_class_id
        WHERE cst.id = $1
        """,
        cst_id,
    )
    if owner is None:
        raise HTTPException(status_code=404, detail="cst not found")
    if owner != caller_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="cst does not belong to caller's org",
        )


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
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> HolidayListResponse:
    _assert_org_match(org_id, org.id)
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
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> HolidayCreated:
    _assert_org_match(org_id, org.id)
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
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> HolidayListResponse:
    await _assert_school_in_org(conn, school_id, org.id)

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
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> HolidayCreated:
    _check_action(payload.action)
    await _assert_school_in_org(conn, school_id, org.id)
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
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> HolidayListResponse:
    await _assert_cst_in_org(conn, cst_id, org.id)
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
    org: OrgContext = Depends(get_current_org),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> HolidayCreated:
    _check_action(payload.action)
    await _assert_cst_in_org(conn, cst_id, org.id)
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
