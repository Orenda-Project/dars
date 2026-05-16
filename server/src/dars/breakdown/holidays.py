"""
F2.10 — Effective-holiday resolution (D-26).

Three-level inheritance:
    Org holidays  (org_holidays, scoped to an academic_year)
  + School overrides where action='add'
  - School overrides where action='remove'
  + CST overrides where action='add'   (teacher sick day)
  - CST overrides where action='remove'

The projector (F2.8) needs the resolved set for a CST + academic year.
The result is a plain `set[date]`.
"""
import logging
from datetime import date
from uuid import UUID

import asyncpg

log = logging.getLogger("breakdown.holidays")


async def resolve_cst_context(
    conn: asyncpg.Connection, cst_id: UUID
) -> tuple[UUID, UUID, UUID, UUID]:
    """
    Walk cst → school_class → (school, academic_year, org).
    Returns (org_id, school_id, academic_year_id, school_class_id).
    Raises ValueError if the CST isn't found.
    """
    row = await conn.fetchrow(
        """
        SELECT sc.org_id, sc.school_id, sc.academic_year_id, sc.id AS school_class_id
        FROM class_subject_teachers cst
        JOIN school_classes sc ON sc.id = cst.school_class_id
        WHERE cst.id = $1
        """,
        cst_id,
    )
    if row is None:
        raise ValueError(f"cst {cst_id} not found")
    return (
        row["org_id"],
        row["school_id"],
        row["academic_year_id"],
        row["school_class_id"],
    )


async def get_org_holidays(
    conn: asyncpg.Connection, academic_year_id: UUID
) -> set[date]:
    rows = await conn.fetch(
        "SELECT date FROM org_holidays WHERE academic_year_id = $1",
        academic_year_id,
    )
    return {r["date"] for r in rows}


async def get_school_overrides(
    conn: asyncpg.Connection, school_id: UUID
) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        SELECT date, action
        FROM school_holiday_overrides
        WHERE school_id = $1
        ORDER BY created_at
        """,
        school_id,
    )


async def get_cst_overrides(
    conn: asyncpg.Connection, cst_id: UUID
) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        SELECT date, action
        FROM cst_holiday_overrides
        WHERE cst_id = $1
        ORDER BY created_at
        """,
        cst_id,
    )


def apply_overrides(
    base: set[date], overrides: list[asyncpg.Record] | list[dict]
) -> set[date]:
    out = set(base)
    for ov in overrides:
        action = ov["action"]
        d = ov["date"]
        if action == "add":
            out.add(d)
        elif action == "remove":
            out.discard(d)
        else:
            log.warning("apply_overrides: ignoring unknown action=%r", action)
    return out


async def get_effective_holidays(
    conn: asyncpg.Connection,
    cst_id: UUID,
) -> set[date]:
    """
    Resolve the full effective holiday set for a CST.
    Reads org + school + CST overrides for the CST's academic year.
    """
    _, school_id, ay_id, _ = await resolve_cst_context(conn, cst_id)
    base = await get_org_holidays(conn, ay_id)
    base = apply_overrides(base, await get_school_overrides(conn, school_id))
    base = apply_overrides(base, await get_cst_overrides(conn, cst_id))
    log.info(
        "get_effective_holidays: cst=%s ay=%s effective=%d",
        cst_id, ay_id, len(base),
    )
    return base


async def get_school_effective_holidays(
    conn: asyncpg.Connection,
    school_id: UUID,
    academic_year_id: UUID,
) -> set[date]:
    """Org + school overrides (no CST-level overrides)."""
    base = await get_org_holidays(conn, academic_year_id)
    return apply_overrides(base, await get_school_overrides(conn, school_id))
