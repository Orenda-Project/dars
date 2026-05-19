"""
F2.8 — Sequence-to-calendar projector (D-7, D-26).

Slots have `position`, not dates. The projector turns a CST's slots
into a list of ProjectedSlot by walking teaching days within the
academic year, skipping holidays and non-timetable days, and honouring
admin-set anchors.

Since D-74 (1 slot = 1 teaching day), the algorithm is straight 1:1:
slot N consumes teaching day N (skipping holidays/weekends). Anchors
still let admins pin specific slots to specific dates.

The pure function `project_schedule(slots, teaching_days, holidays)`
exposes the algorithm for unit testing without DB.

The DB wrapper `project_cst_schedule(conn, cst_id)` looks up:
  - cst → school_class → academic_year (start/end)
  - cst → timetables (day_of_week set)
  - effective holidays (F2.10)
  - class_lesson_slots + class_assessment_slots (merged by position)
"""
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

import asyncpg

from dars.breakdown.holidays import get_effective_holidays, resolve_cst_context

log = logging.getLogger("breakdown.projector")


@dataclass
class SlotInput:
    slot_id: UUID
    slot_kind: str  # 'lesson' | 'assessment'
    position: int
    anchor_date: date | None


@dataclass
class ProjectedSlot:
    slot_id: UUID
    slot_kind: str
    position: int
    projected_date: date | None
    is_anchor: bool = False
    is_overflow: bool = False  # ran out of teaching days
    is_conflict: bool = False  # anchor lands on a non-teaching day


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def compute_teaching_days(
    start_date: date,
    end_date: date,
    weekday_set: set[int],
    holidays: set[date],
) -> list[date]:
    """
    Walk start..end (inclusive) and emit each date whose weekday is in
    weekday_set and which is not a holiday.

    weekday_set: 0=Monday..6=Sunday (matches Python's date.weekday()).
    The migration stores timetable.day_of_week with 0=Monday too.
    """
    if end_date < start_date:
        return []
    out: list[date] = []
    day = start_date
    while day <= end_date:
        if day.weekday() in weekday_set and day not in holidays:
            out.append(day)
        day += timedelta(days=1)
    return out


def project_schedule(
    slots: list[SlotInput],
    teaching_days: list[date],
    *,
    holidays: set[date] | None = None,
) -> list[ProjectedSlot]:
    """
    Walk slots (already ordered by position) and teaching days together.

    Rules:
      - If `anchor_date` is set:
          * If it's in `teaching_days`: skip teaching days up to and
            including the anchor; assign that date. Subsequent slots
            continue from the next teaching day after the anchor.
          * If it's outside the academic year or on a non-teaching day:
            still record the anchor's date but set `is_conflict=True`
            and DO NOT consume any teaching days.
      - If no `anchor_date`: take the next available teaching day. If
        none remain, mark `is_overflow=True` with projected_date=None.
    """
    if holidays is None:
        holidays = set()
    teaching = list(teaching_days)  # mutable copy
    out: list[ProjectedSlot] = []

    for slot in slots:
        if slot.anchor_date is not None:
            anchor = slot.anchor_date
            if anchor in teaching:
                # Skip all teaching days strictly before the anchor.
                idx = teaching.index(anchor)
                teaching = teaching[idx + 1:]
                out.append(ProjectedSlot(
                    slot_id=slot.slot_id,
                    slot_kind=slot.slot_kind,
                    position=slot.position,
                    projected_date=anchor,
                    is_anchor=True,
                ))
            else:
                # Anchor outside teaching set (holiday / non-school day / outside AY).
                out.append(ProjectedSlot(
                    slot_id=slot.slot_id,
                    slot_kind=slot.slot_kind,
                    position=slot.position,
                    projected_date=anchor,
                    is_anchor=True,
                    is_conflict=True,
                ))
            continue

        if not teaching:
            out.append(ProjectedSlot(
                slot_id=slot.slot_id,
                slot_kind=slot.slot_kind,
                position=slot.position,
                projected_date=None,
                is_overflow=True,
            ))
            continue

        day = teaching.pop(0)
        out.append(ProjectedSlot(
            slot_id=slot.slot_id,
            slot_kind=slot.slot_kind,
            position=slot.position,
            projected_date=day,
        ))

    return out


# ---------------------------------------------------------------------------
# DB wrapper
# ---------------------------------------------------------------------------


async def project_cst_schedule(
    conn: asyncpg.Connection,
    cst_id: UUID,
) -> list[ProjectedSlot]:
    log.info("project_cst_schedule: entry cst=%s", cst_id)
    try:
        _, school_id, ay_id, _ = await resolve_cst_context(conn, cst_id)
    except ValueError as e:
        raise ValueError(str(e))

    ay = await conn.fetchrow(
        "SELECT start_date, end_date FROM academic_years WHERE id = $1",
        ay_id,
    )
    if ay is None:
        raise ValueError(f"academic_year {ay_id} not found")

    # Timetable: day_of_week set. Default Mon-Fri (0..4) if no rows.
    tt_rows = await conn.fetch(
        "SELECT day_of_week FROM timetables WHERE cst_id = $1",
        cst_id,
    )
    weekday_set = {r["day_of_week"] for r in tt_rows} or {0, 1, 2, 3, 4}

    holidays = await get_effective_holidays(conn, cst_id)
    teaching_days = compute_teaching_days(
        ay["start_date"], ay["end_date"], weekday_set, holidays
    )

    lesson_rows = await conn.fetch(
        """
        SELECT id, position, anchor_date
        FROM class_lesson_slots
        WHERE cst_id = $1
        ORDER BY position
        """,
        cst_id,
    )
    assess_rows = await conn.fetch(
        """
        SELECT id, position, anchor_date
        FROM class_assessment_slots
        WHERE cst_id = $1
        ORDER BY position
        """,
        cst_id,
    )

    merged: list[SlotInput] = []
    for r in lesson_rows:
        merged.append(SlotInput(
            slot_id=r["id"], slot_kind="lesson",
            position=r["position"], anchor_date=r["anchor_date"],
        ))
    for r in assess_rows:
        merged.append(SlotInput(
            slot_id=r["id"], slot_kind="assessment",
            position=r["position"], anchor_date=r["anchor_date"],
        ))
    merged.sort(key=lambda s: s.position)

    result = project_schedule(merged, teaching_days, holidays=holidays)
    log.info(
        "project_cst_schedule: exit cst=%s slots=%d teaching_days=%d overflow=%d conflicts=%d",
        cst_id, len(result), len(teaching_days),
        sum(1 for p in result if p.is_overflow),
        sum(1 for p in result if p.is_conflict),
    )
    return result
